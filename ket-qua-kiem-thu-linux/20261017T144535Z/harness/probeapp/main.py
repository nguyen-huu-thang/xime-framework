import logging
import os
from xime import Application
from xime.adapters.web import WebAdapter
from xime.adapters.socket import SocketAdapter
from probeapp import config

logging.basicConfig(level=logging.INFO)
app = Application()
app.add_config(config)
app.use(WebAdapter())
if os.environ.get('PROBE_SOCKET'):
    app.use(SocketAdapter())

if __name__ == '__main__':
    if os.environ.get('PROBE_CLUSTER'):
        app.share_load().run()
    else:
        app.run()
