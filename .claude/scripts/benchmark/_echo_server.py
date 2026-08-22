"""Echo TCP tran: khong FastAPI, khong pydantic, khong Xime. Chi co event loop."""
import asyncio
import sys


async def handle(reader, writer):
    try:
        while True:
            data = await reader.read(4096)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionResetError, BrokenPipeError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass

async def main(port: int) -> None:
    loop = asyncio.get_running_loop()
    server = await asyncio.start_server(handle, "127.0.0.1", port)
    print(f"READY loop={type(loop).__module__}.{type(loop).__qualname__}", flush=True)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    nhanh, port = sys.argv[1], int(sys.argv[2])
    if nhanh == "uvloop":
        import uvloop
        asyncio.run(main(port), loop_factory=uvloop.new_event_loop)
    else:
        asyncio.run(main(port))
