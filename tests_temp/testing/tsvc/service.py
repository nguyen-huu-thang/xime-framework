from typing import Protocol


class StoragePort(Protocol):
    """Minimal storage interface - used as a Protocol dep in SampleService."""

    def store(self, value: str) -> None: ...

    def retrieve(self) -> list[str]: ...


class SampleService:
    """
    Minimal service with a Protocol dependency.
    Used to test that TestApplication injects override instances correctly.
    """

    def __init__(self, storage: StoragePort) -> None:
        self.storage = storage

    def save(self, value: str) -> None:
        self.storage.store(value)

    def get_all(self) -> list[str]:
        return self.storage.retrieve()
