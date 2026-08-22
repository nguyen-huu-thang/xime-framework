"""Ba tang HTTP chong len nhau, phuc vu boi CUNG mot uvicorn.

    asgi     : callable ASGI tran - san cua phep do
    fastapi  : FastAPI + mot route tra dict - them routing/serialize cua Starlette
    xime     : Xime WebAdapter - them DI, controller class-based, middleware

Hieu so giua ba dong noi cho biet MOI TANG an bao nhieu, va phan uvloop cai
thien duoc nam o dau trong chong do.

⚠ Ca ba deu chay qua `asyncio.run(server.serve(), loop_factory=...)` - dung
duong Xime di, khong dung `uvicorn.run()` (duong do tu chon loop rieng).
"""
import asyncio
import json
import sys

PORT = int(sys.argv[2])
NHANH = sys.argv[1]
TANG = sys.argv[3]

_BODY = json.dumps({"ok": "1"}).encode()


async def app_asgi(scope, receive, send):
    if scope["type"] != "http":
        return
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"application/json"),
                            (b"content-length", str(len(_BODY)).encode())]})
    await send({"type": "http.response.body", "body": _BODY})


def lam_app():
    if TANG == "asgi":
        return app_asgi
    if TANG == "fastapi":
        from fastapi import FastAPI
        f = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

        @f.get("/ping")
        async def ping() -> dict[str, str]:
            return {"ok": "1"}

        return f
    raise SystemExit(f"tang khong biet: {TANG}")


async def main() -> None:
    import uvicorn
    loop = asyncio.get_running_loop()
    cfg = uvicorn.Config(lam_app(), host="127.0.0.1", port=PORT,
                         log_level="warning", access_log=False)
    server = uvicorn.Server(cfg)
    print(f"READY loop={type(loop).__module__}.{type(loop).__qualname__}", flush=True)
    await server.serve()


if NHANH == "uvloop":
    import uvloop
    asyncio.run(main(), loop_factory=uvloop.new_event_loop)
else:
    asyncio.run(main())
