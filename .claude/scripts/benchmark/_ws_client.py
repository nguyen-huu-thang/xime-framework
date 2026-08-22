"""Client WebSocket cho bench: mot ket noi song lau + nhieu ket noi cung luc."""
import asyncio
import sys
import time

import websockets

PORT, TIN, KET_NOI = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
URL = f"ws://127.0.0.1:{PORT}/echo"


async def main() -> None:
    async with websockets.connect(URL) as w:
        for i in range(200):                       # lam nong
            await w.send(f"w{i}")
            await w.recv()
        t0 = time.perf_counter()
        for i in range(TIN):
            await w.send(f"m{i}")
            await w.recv()
        tin_giay = TIN / (time.perf_counter() - t0)

    async def mot(i: int) -> str:
        async with websockets.connect(URL) as w:
            await w.send(f"c{i}")
            return await w.recv()

    t0 = time.perf_counter()
    await asyncio.gather(*[mot(i) for i in range(KET_NOI)])
    bat_tay_giay = KET_NOI / (time.perf_counter() - t0)
    print(f"{tin_giay:.0f} {bat_tay_giay:.0f}")


asyncio.run(main())
