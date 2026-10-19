import os

from tests_temp.bootstrap.signal_sample import config
from xime import Application
from xime.adapters.socket import SocketAdapter
from xime.adapters.web import WebAdapter

if os.environ.get('SIGNAL_TEST_ASYNCIO'):
    import xime.core.bootstrap._supervisor as supervisor
    supervisor.worker_loop_factory = lambda sockets: None

app = Application().add_config(config).use(WebAdapter()).use(SocketAdapter())

if __name__ == '__main__':
    if os.environ.get('SIGNAL_CLUSTER'):
        app.share_load().run()
    else:
        app.run()
