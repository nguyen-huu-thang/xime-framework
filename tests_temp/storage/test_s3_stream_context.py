"""The real StreamingBody context returns the raw response, not the wrapper.

Context thật trả response thô; đọc theo chunk phải giữ wrapper StreamingBody.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from xime.starters.s3 import S3FileStorage


class WrapperBody:
    def __init__(self, payload=b'', error=None):
        self.payload = payload
        self.error = error
        self.sizes = []
        self.entered = 0
        self.exits = []
        self.reading = asyncio.Event()

    async def __aenter__(self):
        self.entered += 1
        return SimpleNamespace(read=AsyncMock(side_effect=TypeError('raw response has no read(size)')))

    async def __aexit__(self, kind, error, traceback):
        self.exits.append(kind)
        return False

    async def read(self, size=-1):
        self.reading.set()
        self.sizes.append(size)
        if self.error == 'wait':
            await asyncio.Event().wait()
        if self.error is not None:
            raise self.error
        if size < 0:
            chunk, self.payload = self.payload, b''
        else:
            chunk, self.payload = self.payload[:size], self.payload[size:]
        return chunk


def storage_for(body):
    client = SimpleNamespace(get_object=AsyncMock(return_value={'Body': body}))
    provider = SimpleNamespace(client=client, bucket='synthetic-test-bucket')
    return S3FileStorage(provider), client


@pytest.mark.asyncio
async def test_whole_get_also_keeps_wrapper_validation():
    body = WrapperBody(b'whole-object')
    storage, _ = storage_for(body)
    assert await storage.get('key') == b'whole-object'
    assert body.sizes == [-1]
    assert body.entered == 1 and body.exits == [None]


@pytest.mark.asyncio
@pytest.mark.parametrize('offset,length', [(0, None), (100, 17)])
async def test_reads_wrapper_instead_of_context_return_value(offset, length):
    payload = b'x' * (150_000 if length is None else length)
    body = WrapperBody(payload)
    storage, client = storage_for(body)
    chunks = [part async for part in storage.open_stream('key', offset=offset, length=length)]
    assert b''.join(chunks) == payload
    assert all(0 < size <= 65536 for size in body.sizes)
    assert body.entered == 1 and body.exits == [None]
    arguments = {'Bucket': 'synthetic-test-bucket', 'Key': 'key'}
    if length is not None:
        arguments['Range'] = f'bytes={offset}-{offset+length-1}'
    client.get_object.assert_awaited_once_with(**arguments)


@pytest.mark.asyncio
async def test_read_error_propagates_and_releases_response():
    error = RuntimeError('synthetic read failure')
    body = WrapperBody(error=error)
    storage, _ = storage_for(body)
    with pytest.raises(RuntimeError, match='synthetic read failure') as caught:
        _ = [part async for part in storage.open_stream('key')]
    assert caught.value is error
    assert body.exits == [RuntimeError]


@pytest.mark.asyncio
async def test_cancellation_releases_response():
    body = WrapperBody(error='wait')
    storage, _ = storage_for(body)

    async def drain():
        return [part async for part in storage.open_stream('key')]

    task = asyncio.create_task(drain())
    try:
        await asyncio.wait_for(body.reading.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert body.exits == [asyncio.CancelledError]
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_consumer_closing_stream_releases_response():
    body = WrapperBody(b'x'*150_000)
    storage, _ = storage_for(body)
    stream = storage.open_stream('key')
    assert await anext(stream)
    await stream.aclose()
    assert body.exits == [GeneratorExit]
