import asyncio
import json
import logging
import os
from pathlib import Path

from pydantic import BaseModel

from xime.adapters.socket import command
from xime.adapters.web import get
from xime.core.context import request_context


class LifecycleProbe:
    async def post_construct(self) -> None:
        self.record('started')

    async def pre_destroy(self) -> None:
        self.record('destroyed')
        logging.warning('signal-probe-pre-destroy pid=%s', os.getpid())

    def record(self, event: str) -> None:
        with Path('lifecycle.jsonl').open('a') as stream:
            stream.write(json.dumps({'event': event, 'pid': os.getpid()}) + '\n')


class ProbeController:
    @get('/probe')
    async def probe(self) -> dict:
        loop = asyncio.get_running_loop()
        return {'pid': os.getpid(), 'loop': type(loop).__module__ + '.' + type(loop).__name__}


class ProbeRequest(BaseModel):
    value: str


class ProbeReply(BaseModel):
    value: str
    pid: int
    peer_pid: int
    peer_uid: int


class UnixController:
    @command('probe')
    async def probe(self, request: ProbeRequest) -> ProbeReply:
        return ProbeReply(value=request.value, pid=os.getpid(),
                          peer_pid=request_context.get('peer_pid'),
                          peer_uid=request_context.get('peer_uid'))
