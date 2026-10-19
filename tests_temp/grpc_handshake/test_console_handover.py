from tests_temp.grpc_handshake.test_bootstrap import run_code


def test_custom_stderr_console_requires_handover_and_bypasses_pipe():
    result = run_code('''
import logging
from xime import Application, BindingConfig
from xime.core.config import RuntimeConfig
from xime.core.exception.framework import StartupException
from xime.observability import prepare_grpc_handshake_logging
cfg=RuntimeConfig.from_dict({"grpc":{"handshake_logging":{"enabled":True}},"logging":{"enabled":False}})
prepare_grpc_handshake_logging(runtime=cfg)
handler=logging.StreamHandler()
logging.getLogger().addHandler(handler)
bad=Application(binding=BindingConfig())
try:
    bad._start_logging(cfg)
except StartupException as exc:
    assert "use_logging_console" in str(exc)
else:
    raise AssertionError("unmanaged pipe console accepted")
managed=RuntimeConfig.from_dict({"grpc":{"handshake_logging":{"enabled":True}}})
app=Application(binding=BindingConfig()).use_logging_console(handler)
app._start_logging(managed)
assert handler.stream.fileno()!=2
logging.error("SAFE_CONSOLE_HANDOVER")
app._stop_logging()
assert handler.stream.fileno()==2
''')
    assert result.stderr.count("SAFE_CONSOLE_HANDOVER") == 1
