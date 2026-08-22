"""Y het `_echo_server.py` nhung dung PROTOCOL API thay vi Stream API.

⭐ Day la khac biet quan trong nhat khi doc so lieu uvloop ngoai internet: cac
con so "2-4x" cua uvloop gan nhu luon do bang Protocol API. Stream API dung
them mot lop Python (StreamReader/StreamWriter, drain, future moi luot) nam
NGOAI pham vi uvloop thay the duoc - nen lai bi pha loang.
"""
import asyncio
import sys


class Echo(asyncio.Protocol):
    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        self.transport.write(data)


async def main(port: int) -> None:
    loop = asyncio.get_running_loop()
    server = await loop.create_server(Echo, "127.0.0.1", port)
    print(f"READY loop={type(loop).__module__}.{type(loop).__qualname__}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    nhanh, port = sys.argv[1], int(sys.argv[2])
    if nhanh.startswith("uvloop"):
        import uvloop
        asyncio.run(main(port), loop_factory=uvloop.new_event_loop)
    else:
        asyncio.run(main(port))
