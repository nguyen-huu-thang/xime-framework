"""Khai bảng tham chiếu - cha đọc danh sách này để cấp vùng nhớ TRƯỚC khi dựng DI."""

from xime.core.refdata import configure_refdata

from sample_app.refdata.keys import KeyTable

configure_refdata([KeyTable])
