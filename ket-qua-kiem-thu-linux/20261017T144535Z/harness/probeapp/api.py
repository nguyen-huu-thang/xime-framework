import asyncio
import os
from pydantic import BaseModel
from xime.adapters.web import get, ws, WebSocketHandler
from xime.adapters.socket import command
from xime.core.context import request_context

def info():
    loop = asyncio.get_running_loop()
    return {'pid': os.getpid(), 'loop': type(loop).__module__ + '.' + type(loop).__qualname__}

class ProbeController:
    @get('/probe')
    async def probe(self) -> dict:
        return info()

@ws('/echo')
class EchoHandler(WebSocketHandler):
    async def on_connect(self, socket):
        await socket.accept()
        await socket.send_json(info())

    async def on_message(self, socket, text):
        await socket.send_text(text)

class ProbeRequest(BaseModel):
    value: str

class ProbeReply(BaseModel):
    pid: int
    loop: str
    value: str
    peer_uid: int
    peer_pid: int

class SocketProbeController:
    @command('probe')
    async def probe(self, request: ProbeRequest) -> ProbeReply:
        return ProbeReply(**info(), value=request.value, peer_uid=request_context.get('peer_uid'), peer_pid=request_context.get('peer_pid'))
