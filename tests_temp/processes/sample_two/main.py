"""App một tiến trình, **hai** server web - khuôn của khối `process:`."""

from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

from sample_two import config

app = Application()
app.add_config(config)
app.use(WebAdapter("public")).use(WebAdapter("admin"))

if __name__ == "__main__":
    app.run()
