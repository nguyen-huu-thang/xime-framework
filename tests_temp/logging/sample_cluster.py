"""No network listener or app service. Only fixture adapters and file commands."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from types import ModuleType

from xime.core.bootstrap import Application
from xime.core.bootstrap.adapter import Adapter
from xime.core.config import BindingConfig


class Probe(Adapter, scaling="replicated"):
    adapter_kind = "probe"
    adapter_id = "default"

    def assign_slot(self, slot):
        self.slot = slot

    async def start(self, app):
        self.app = app
        self.stopped = asyncio.Event()

    async def serve(self):
        logging.getLogger("probe").info("worker-ready")
        pid = os.getpid()
        Path(f"{pid}.ready").touch()
        batches = 0
        while not self.stopped.is_set():
            command = Path(f"{pid}.emit")
            if command.exists():
                command.unlink()
                for index in range(100):
                    logging.getLogger("probe").debug("item", extra={"sequence": index})
                logging.getLogger("probe").info("batch-done")
                batches += 1
                Path(f"{pid}.done").write_text(str(batches), encoding="utf-8")
            if Path(f"{pid}.die").exists():
                await asyncio.sleep(0.2)
                os._exit(23)
            await asyncio.sleep(0.02)

    async def stop(self):
        if hasattr(self, "stopped"):
            self.stopped.set()


class Primary(Adapter, scaling="singleton"):
    adapter_kind = "primaryprobe"
    adapter_id = "default"

    def assign_slot(self, slot):
        pass

    async def start(self, app):
        self.stopped = asyncio.Event()
        logging.getLogger("probe").info("primary-started")
        Path(f"{os.getpid()}.primary").touch()

    async def serve(self):
        await self.stopped.wait()

    async def stop(self):
        if hasattr(self, "stopped"):
            self.stopped.set()


config = ModuleType("probe_config")
config.dependency = BindingConfig()
app = Application().add_config(config).use(Probe()).use(Primary())

if __name__ == "__main__":
    app.share_load().run()
