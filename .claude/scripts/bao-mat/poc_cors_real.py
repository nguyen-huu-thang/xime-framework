"""PoC 12 - CORS thật của 24 app: origin IP công cộng có được cấp quyền kèm cookie?"""
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.testclient import TestClient

async def me(request):
    return JSONResponse({"user": "chu-tiem", "doanh_thu": 123456789})

app = Starlette(routes=[Route("/api/v1/me", me)])
# Sao y cấu hình đang chạy: configure_cors(allow_credentials=True, methods *, headers *)
# + khối cors.* trong application.yml của 24 codebase
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8171"],
    allow_origin_regex=r'^http://(localhost|(\d{1,3}\.){3}\d{1,3})(:\d+)?$',
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
client = TestClient(app)

for origin in [
    "http://localhost:8171",
    "http://203.0.113.66",          # IP CÔNG CỘNG của kẻ tấn công
    "http://8.8.8.8:9999",
    "https://ke-tan-cong.example",  # tên miền -> phải bị chặn
]:
    r = client.get("/api/v1/me", headers={"Origin": origin, "Cookie": "refresh=abc"})
    aco = r.headers.get("access-control-allow-origin")
    acc = r.headers.get("access-control-allow-credentials")
    ok = (aco == origin and acc == "true")
    print(f"  Origin {origin:32} -> ACAO={aco!r:34} ACAC={acc!r:8} {'<== ĐỌC ĐƯỢC DỮ LIỆU' if ok else ''}")
