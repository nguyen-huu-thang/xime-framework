from xime.adapters.web.routing import get, post


class UserController:
    prefix = "/users"
    tags = ["users"]

    @get("")
    async def list_users(self) -> list:
        return []

    @post("", status_code=201)
    async def create_user(self) -> dict:
        return {"created": True}
