from sample.repository.user_repository import UserRepository


class UserService:
    def __init__(self, repository: UserRepository):
        self.repository = repository

    def get_user(self, user_id: int) -> dict:
        return self.repository.find_by_id(user_id)
