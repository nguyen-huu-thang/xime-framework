"""Bật hai endpoint sức khoẻ - **phải khai mới có**, đó là cả điểm của B+."""

from xime.adapters.web import configure_health
from xime.adapters.web.routing import configure_controllers

configure_controllers("sample_cluster.api")
configure_health()
