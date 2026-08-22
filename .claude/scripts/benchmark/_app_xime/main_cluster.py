"""Ban share_load() cua app bench - dung cho bench_scale.py."""
from _app_xime import config
from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

app = Application()
app.add_config(config)
app.use(WebAdapter())

if __name__ == "__main__":
    app.share_load().run()
