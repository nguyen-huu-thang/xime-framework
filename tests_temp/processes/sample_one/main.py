"""App một tiến trình, một cổng - khuôn của 58/69 file cấu hình hiện có.

Không gọi `share_load()`, nên nó đọc khoá phẳng `server:` như trước 0.8. Khoá đó
nay được **dịch** thành `process.web.default`, và bài test đi qua đường dịch này
bằng một tiến trình thật.
"""

from xime.adapters.web import WebAdapter
from xime.core.bootstrap import Application

from sample_one import config

app = Application()
app.add_config(config)
app.use(WebAdapter())

if __name__ == "__main__":
    app.run()
