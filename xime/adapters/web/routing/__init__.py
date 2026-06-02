"""
xime.adapters.web.routing — HTTP route decorators and controller registration.

Usage:
    from xime.adapters.web.routing import get, post, put, patch, delete
    from xime.adapters.web.routing import configure_controllers

Example:
    class UserController:
        prefix = "/users"
        tags = ["users"]

        def __init__(self, use_case: UserUseCase) -> None:
            self._use_case = use_case

        @get("/{user_id}", response_model=UserResponse)
        async def get_user(self, user_id: int) -> UserResponse:
            return await self._use_case.get(user_id)
"""

from adapters.web.routing import (
    configure_controllers,
    delete,
    get,
    patch,
    post,
    put,
)

__all__ = [
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "configure_controllers",
]
