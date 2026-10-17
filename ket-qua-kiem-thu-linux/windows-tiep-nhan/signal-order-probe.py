"""Instrument cleanup order; this is not a native Linux SIGTERM test."""
import asyncio
from contextlib import contextmanager

from xime.adapters.web import WebAdapter

steps = []


class Server:
    should_exit = False
    servers = []

    @contextmanager
    def capture_signals(self):
        steps.append("enter capture")
        yield
        steps.append("replay signal")

    async def main_loop(self):
        steps.append("main loop finished")

    async def shutdown(self, sockets=None):
        steps.append("web shutdown")


adapter = WebAdapter("default")
adapter._server = Server()
asyncio.run(adapter.serve())
print(" -> ".join(steps))
assert steps.index("replay signal") < steps.index("web shutdown")
