"""Client LUON chay loop mac dinh - de bien duy nhat doi la loop cua SERVER."""
import asyncio
import sys
import time

PORT, CONN, ROUNDS = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
PAYLOAD = b"x" * 256

async def mot_ket_noi() -> None:
    r, w = await asyncio.open_connection("127.0.0.1", PORT)
    try:
        for _ in range(ROUNDS):
            w.write(PAYLOAD)
            await w.drain()
            await r.readexactly(len(PAYLOAD))
    finally:
        w.close()
        try:
            await w.wait_closed()
        except Exception:
            pass

async def main() -> None:
    await asyncio.gather(*[mot_ket_noi() for _ in range(max(2, CONN // 5))])  # lam nong
    t0 = time.perf_counter()
    await asyncio.gather(*[mot_ket_noi() for _ in range(CONN)])
    print(f"{CONN * ROUNDS / (time.perf_counter() - t0):.0f}")

asyncio.run(main())
