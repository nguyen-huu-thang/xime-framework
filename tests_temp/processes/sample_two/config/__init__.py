"""Khai hết những gì phải chạy, và **thứ tự là thứ tự viết ra**.

Cơ chế cũ nạp theo thứ tự alphabet của `pkgutil`, không ai chọn và không ai thấy.
Thêm một file config mới mà quên thêm dòng import thì nó không chạy - và cái quên
đó **nhìn thấy được ngay trong file này**, khác hẳn một file nằm im trong thư mục.
"""

from sample_two.config.dependency import dependency

from sample_two.config import web  # noqa: F401  - chạy configure_* lúc import

__all__ = ["dependency"]
