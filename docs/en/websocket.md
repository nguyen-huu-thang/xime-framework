# WebSocket

**English** | [Tiếng Việt](../vn/websocket.md)

[← Routing](routing.md) · **WebSocket** · [Socket Adapter →](socket-adapter.md)

---

## 1. Overview

The WebSocket adapter gives you a long-lived, two-way connection on the application's own HTTP port. Unlike `@get`/`@post`, which handle one request and answer it, a WebSocket handler lives for the whole connection and receives one message at a time.

Three things the framework owns, so business code does not have to:

| | |
|---|---|
| **Lifecycle** | accept, receive loop, disconnect, context cleanup - all inside `WebSocketHandler` |
| **Authentication** | the JWT is verified **before** the handler is entered, with the same keys and the same rules as the HTTP path |
| **Expiry** | the connection is closed when the token that opened it expires |

> ⚠ New in 0.7.2. Before that, `WebSocketHandler` existed but had **no route registration path at all**, and `JwtAuthMiddleware` skipped every WebSocket connection - so a hand-wired WebSocket route accepted everyone, token or not.

---

## 1b. What you need to install

```bash
pip install 'xime[web]'
```

That is all. The `web` extra pulls `uvicorn[standard]`, which includes the
WebSocket library (`websockets`) uvicorn needs for the handshake.

⚠ **With plain `uvicorn`, `@ws` routes die silently.** Uvicorn does not install a
WebSocket library on its own, and without one the handshake **fails** - the
routes still register, FastAPI still accepts them, and the failure only surfaces
on a real user's first connection.

Since `0.8.1`, Xime **warns at startup** when the application has `@ws` routes
but the environment has no library:

```text
WARNING | xime.web.ws | 3 WebSocket route(s) registered but uvicorn has no
                        WebSocket implementation available (neither
                        'websockets' nor 'wsproto'), so every handshake on them
                        will fail with nothing else logged. Install one with:
                        pip install "xime[web]"   (or: pip install
                        "uvicorn[standard]")
```

It fires **only when the application actually has `@ws` routes**, and it warns
rather than refusing to start: this is a non-standard install, not a
configuration error worth blocking on.

Installing `wsproto` instead of `websockets` works too - Xime asks what uvicorn
actually uses rather than listing package names.

---

## 2. Writing a handler

```python
# api/ws/chat.py
from xime.adapters.web import WebSocketHandler, ws
from xime.core.security import identity


@ws("/chat")
class ChatHandler(WebSocketHandler):
    def __init__(self, rooms: RoomService) -> None:
        self.rooms = rooms

    async def on_connect(self, socket) -> None:
        await super().on_connect(socket)          # accept + echo the subprotocol
        await self.rooms.join(identity.get())

    async def on_message(self, socket, data: str) -> None:
        await self.rooms.broadcast(data)

    async def on_disconnect(self, socket, code: int) -> None:
        await self.rooms.leave(identity.get())
```

The class is built by the DI container like any controller, so its package must appear in **both** declarations:

```python
# config/dependency.py
dependency.scan("my_service.api.ws")

# config/web.py
configure_controllers("my_service.api.ws")
```

Four methods to override, none of them mandatory:

| Method | When it runs |
|---|---|
| `on_connect(socket)` | The client just connected. Default: accept and echo the negotiated subprotocol |
| `on_message(socket, data)` | A text message arrived |
| `on_bytes(socket, data)` | A binary message arrived |
| `on_disconnect(socket, code)` | The connection ended, for any reason |

⚠ If `on_connect` raises, `on_disconnect` does **not** run - the connection was never established.

---

## 3. Authentication

### 3.1. The token travels in a subprotocol

A browser **cannot set headers** on `new WebSocket(...)`. That is a platform limit, not a design choice - so the token has to travel inside something the handshake already carries.

Xime uses `Sec-WebSocket-Protocol`, the industry's answer (Kubernetes and Firebase both do this). Unlike a query string it **never reaches proxy access logs, browser history, or the `Referer` header**.

```js
const socket = new WebSocket(url, ["xime.bearer." + token, "xime"]);
```

The client offers **two** subprotocols: one carrying the token, one being the real protocol. The server verifies the token, accepts, and **echoes the other one**:

```js
socket.protocol   // "xime"  - never the entry holding the token
```

⚠ Only the **first** `xime.bearer.` entry is read. Two of them is a malformed request, not a choice for the server to make: picking one would mean the server decides which of two identities the caller meant.

### 3.2. The default is to demand a token

Once `configure_jwt()` has been called, **every** `@ws` path demands a valid token. No token, bad signature, expired token, missing identity claim - all four are closed with code **3000** (`Unauthorized` in the IANA registry) and **without saying which step failed**: a handshake has no response body to carry a reason, the client's action is identical in all four cases (get a valid token, retry), and splitting them would only tell an attacker which half of the guess was right. The real reason goes to the **server log**.

⭐ **Authentication runs in the route registrar, not in `on_connect`.** This is the design point worth remembering: putting it in `on_connect` would make it a default a subclass silently removes by overriding that method, and a guard that disappears exactly when you write the code the docs told you to write is not a guard. Overriding `on_connect` - or even `handle()` - **cannot skip authentication**.

### 3.3. Open paths

A public WebSocket route lists its path in `public_paths` - the **same list HTTP uses**, because "this path is open" should mean one thing in an application, not two:

```python
configure_jwt(JwtMiddlewareConfig(
    key_context=...,
    public_paths=["/health", "/ws/public-feed"],
))
```

### 3.4. What if there is no JWT at all

An application that never calls `configure_jwt()` keeps its WebSocket routes open, exactly as its HTTP routes are. That is consistent behaviour, not a hole - but the framework logs a **WARNING** at startup naming every such handler. The silence around this fact is precisely why the old hole lived so long.

---

## 4. Token expiry mid-connection

An HTTP request checks its token once. A WebSocket connection lives for hours.

By default the framework **closes the connection the moment the token expires** (close code 3000, the same as a refused handshake - because the client does exactly one thing in both cases: get a fresh token and reconnect).

Without this, revoking a token cannot end a WebSocket session: a socket opened this morning still speaks for an account disabled at noon.

Turn it off if you manage the lifetime yourself:

```python
@ws("/chat")
class ChatHandler(WebSocketHandler):
    close_on_token_expiry = False
```

⚠ A token with no `exp` gives the watchdog no deadline - and such a token **never expires**. Forbid it with `JwtMiddlewareConfig(require=["exp"])`.

---

## 5. Context and identity

Inside the handler, everything familiar is there:

```python
from xime.core.context import request_context
from xime.core.security import identity
from xime.starters.jwt import JWT_CLAIMS

identity.get()                        # the token's sub
request_context.get(JWT_CLAIMS)       # every claim, no second decode
request_context.get("connection_id")  # this connection's own id
```

`WebSocketHandler` sets up and tears down its own context, because `RequestContextMiddleware` - like every ASGI middleware - only runs for HTTP scopes.

---

## 6. Multiple servers

Same as controllers: declare `server_id` so the handler attaches only to the `WebAdapter` carrying that id.

```python
@ws("/admin/stream")
class AdminStream(WebSocketHandler):
    server_id = "admin"
```

---

## 7. Boundaries - what this adapter does NOT do

| Not done | Why |
|---|---|
| **Check the `Origin` header** | Browsers do not apply CORS to a WebSocket handshake, so defending against *Cross-Site WebSocket Hijacking* is manual work - **but only when authentication rides on cookies**. Here the token travels in a subprotocol, and another site simply **does not have the token** to offer. The risk is closed at its root rather than skipped.<br>⚠ The day anyone adds cookie-based WebSocket authentication, an `Origin` check becomes **mandatory**, not optional |
| **Refresh a token over the socket** | Not yet. The connection closes on expiry and the client reconnects with a fresh token |
| **Hand-registered WebSocket routes** | Calling `app.add_api_websocket_route(...)` on FastAPI directly bypasses everything above, authentication included. Use `@ws` |

---

[← Routing](routing.md) · **WebSocket** · [Socket Adapter →](socket-adapter.md)
