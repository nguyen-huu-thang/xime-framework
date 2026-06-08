from __future__ import annotations

import abc

"""Transport-neutral stream interfaces.

A controller method declares `upload: UploadStream` / `download: DownloadStream`
to opt into streaming. Each transport (Socket, Code-First gRPC) supplies its own
concrete implementation, but controllers depend only on these abstract types —
so the same controller serves multiple transports unchanged.
Controller chỉ phụ thuộc abstract type; mỗi transport cấp implementation riêng,
nhờ đó cùng một controller phục vụ nhiều transport.
"""


class UploadStream(abc.ABC):
    """An inbound chunk stream the handler reads from (client → server).

        async for chunk in upload: ...
        chunk = await upload.read()   # None at end-of-stream
    """

    @abc.abstractmethod
    def __aiter__(self) -> "UploadStream":
        ...

    @abc.abstractmethod
    async def __anext__(self) -> bytes:
        ...

    @abc.abstractmethod
    async def read(self) -> bytes | None:
        """Return the next chunk, or None when the stream is exhausted."""
        ...


class DownloadStream(abc.ABC):
    """An outbound chunk stream the handler writes to (server → client).

        await download.write(chunk)
    """

    @abc.abstractmethod
    async def write(self, chunk: bytes) -> None:
        ...
