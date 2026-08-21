"""
Web file helpers - stream stored objects to/from HTTP without buffering.

These are plain helper functions called from inside controller methods; they are
NOT scanned into the DI container. Pair them with a StorageService backend
(local / s3) bound in config/dependency.py.

    from xime.adapters.web.files import stream_object, save_upload, PayloadTooLarge

    class FileController:
        def __init__(self, storage: StorageService) -> None:
            self._storage = storage

        @get("/files/{key:path}")
        async def download(self, key: str, request: Request):
            return await stream_object(self._storage, key, request=request)

        @post("/files/{key:path}")
        async def upload(self, key: str, file: UploadFile):
            await save_upload(self._storage, key, file, max_bytes=50 * 1024 * 1024)
            return {"key": key}
"""

from ._download import stream_object
from ._errors import PayloadTooLarge
from ._upload import DEFAULT_MAX_BYTES, save_upload

__all__ = [
    "stream_object",
    "save_upload",
    "DEFAULT_MAX_BYTES",
    "PayloadTooLarge",
]
