"""
Controller routing layer for Xime Framework.

Provides HTTP route decorators and the configure_controllers() function.
Follows the same explicit-call pattern as configure_openapi() and configure_jwt().

Usage:
    # api/rest/user_controller.py
    from adapters.web.routing import get, post, delete

    class UserController:
        prefix = "/users"
        tags = ["users"]

        def __init__(self, use_case: UserUseCase) -> None:
            self._use_case = use_case

        @get("/{user_id}", response_model=UserResponse)
        async def get_user(self, user_id: int) -> UserResponse:
            return await self._use_case.get(user_id)

    # config/routing.py
    from adapters.web.routing import configure_controllers
    configure_controllers("api.rest")
"""

from ._config import configure_controllers
from ._decorators import delete, get, patch, post, put

__all__ = [
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "configure_controllers",
]
