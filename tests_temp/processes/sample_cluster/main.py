"""App dùng cho phép đo giai đoạn 6: `run_once`, thăng cấp, watchdog, sức khoẻ.

Tách khỏi `sample_app` để những phép đo của giai đoạn 3 và 5 không phải gánh
thêm một scheduler và một job - hai app nhỏ dễ đọc hơn một app làm mọi thứ.
"""

from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

from sample_cluster import config
from sample_cluster.adapters.breakable import BreakableAdapter
from sample_cluster.adapters.fragile import FragileAdapter

app = Application()
app.add_config(config)
app.use(WebAdapter())
app.use(FragileAdapter())
app.use(BreakableAdapter())

if __name__ == "__main__":
    app.share_load().run()
