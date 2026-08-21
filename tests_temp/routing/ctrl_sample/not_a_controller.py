class NotAController:
    """Class thông thường - không có route decorator → scanner bỏ qua."""

    async def do_something(self) -> None:
        pass

    def helper(self) -> str:
        return "help"
