class ConfigService:
    """Service không có dependency - kiểm tra trường hợp class không có __init__ params."""

    def get_value(self, key: str) -> str:
        return "default"
