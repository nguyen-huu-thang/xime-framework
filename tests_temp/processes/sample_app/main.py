"""Khuôn `main.py` của một app Xime - bản chốt ở mục 5.1 của thiết kế.

⭐ Ba dòng giữa nằm ở **MỨC MODULE**, không nằm trong `if __name__`. Đó là điều
kiện để tiến trình con dựng lại được ứng dụng: con chạy **lại chính file này**,
và `if __name__ == "__main__"` không kích hoạt ở đó.
"""

from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

from sample_app import config

app = Application()
app.add_config(config)
app.use(WebAdapter())

if __name__ == "__main__":
    app.share_load().run()
