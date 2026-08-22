import os

from xime.adapters.web import WebSocketHandler, get, ws


class BenchController:
    prefix = ""

    @get("/ping")
    async def ping(self) -> dict[str, str]:
        """Duong nong cua phep do: cang it viec cang tot."""
        return {"ok": "1"}

    @get("/pid")
    async def pid(self) -> dict[str, int]:
        """Ai dang tra loi.

        bench_scale.py dem pid de biet CO BAO NHIEU tien trinh that su nhan
        viec - con so rps khong thay duoc cho nay: mot cum 4 tien trinh ma chi
        2 cai tra loi van cho ra mot con so rps trong binh thuong.
        """
        return {"pid": os.getpid()}


@ws("/echo")
class EchoWs(WebSocketHandler):
    """Route @ws phuc vu HAI viec.

    1. `bench_ws.py` do thong luong tin nhan tren ket noi song lau - hinh dang
       tai nguoc han REST, va la cho uvloop that su co lai.
    2. Kich hoat canh bao "co route @ws ma uvicorn khong co thu vien WebSocket"
       cua 0.8.1: canh bao do chi kem khi app THAT SU co route @ws.
    """

    async def on_message(self, socket, data: str) -> None:
        await socket.send_text(f"echo:{data}")
