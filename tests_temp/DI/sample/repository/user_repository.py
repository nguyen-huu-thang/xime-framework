class UserRepository:
    def find_by_id(self, user_id: int) -> dict:
        return {"id": user_id, "name": "Test User"}

    def save(self, user: dict) -> None:
        pass
