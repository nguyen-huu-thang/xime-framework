"""grpcio 1.72.1 uses handshake_manager before the same metadata tail."""
from collections import Counter

import pytest

from xime.observability._grpc_native import NativeCollector
from xime.observability._grpc_parser import NativeFramer, parse_failure


def native_record(status='UNKNOWN:HTTP_REQUEST', source='handshaker.cc:142', manager='0xaBcD'):
    return (
        f'I0000 00:00:1.000001    12 {source}] handshake_manager {manager}: error={status}'
        ' shutdown=false index=2, args={endpoint=0x456, args={'
        'grpc.internal.server_credentials=0x789, '
        'grpc.internal.endpoint_peer_address=ipv4:127.0.0.1:45678, '
        'grpc.internal.endpoint_local_address=ipv4:127.0.0.1:50051}, '
        'read_buffer.Length()=0, exit_early=0}\n'
    ).encode()


@pytest.mark.parametrize('status', ['UNKNOWN:HTTP_REQUEST',
    'UNKNOWN:HTTP_REQUEST grpc.internal.endpoint_peer_address=ipv4:192.0.2.9:1'])
@pytest.mark.parametrize('manager', ['0xaBcD', '00000203F46C1090', 'F46C1090'])
def test_legacy_status_uses_only_metadata_endpoints(status, manager):
    failure = parse_failure(native_record(status, manager=manager))
    assert failure is not None
    assert failure.remote == ('127.0.0.1', 45678)
    assert failure.local == ('127.0.0.1', 50051)
    assert failure.cause == 'http_request'


@pytest.mark.parametrize('manager', ['0xaBcD', '00000203F46C1090', 'F46C1090'])
def test_legacy_frame_survives_every_byte_boundary(manager):
    records, forwarded, counters = [], [], Counter()
    framer = NativeFramer(limit=65536, quiet=True, forward=forwarded.append,
                         record=records.append, count=lambda key: counters.update([key]))
    raw = native_record(manager=manager) + native_record('OK', manager=manager)
    for byte in raw:
        framer.feed(bytes([byte]))
    framer.flush_partial()
    assert records == [native_record(manager=manager), native_record('OK', manager=manager)]
    assert not counters


@pytest.mark.parametrize('manager', ['0xaBcD', '00000203F46C1090', 'F46C1090'])
def test_legacy_success_is_not_reported_as_parse_loss(manager):
    class Collector:
        def __init__(self):
            self.counters = Counter()

        def _increment(self, name):
            self.counters.update([name])

    collector = Collector()
    NativeCollector._record(collector, native_record('OK', manager=manager))
    assert not collector.counters


@pytest.mark.parametrize('source,manager', [('unknown.cc:142','0xabc'),
                                         ('handshaker.cc:142','not-a-native-pointer'),
                                         ('handshaker.cc:142','00000203F46C109'),
                                         ('handshaker.cc:142','00000203F46C109Z')])
def test_unknown_legacy_prefix_is_not_accepted(source, manager):
    assert parse_failure(native_record(source=source, manager=manager)) is None
