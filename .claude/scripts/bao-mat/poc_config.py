import sys, os, tempfile
sys.path.insert(0, r"d:/code/xime/xime framework")
from xime.core.config.runtime import RuntimeConfig
from xime.core.config.loader import YamlConfigLoader, detect_env

print("="*72); print("PoC 9 - RuntimeConfig in ra secret khi log/repr?"); print("="*72)
cfg = RuntimeConfig.from_dict({
    "env": "production",
    "database": {"url": "postgresql://xime:SIEU_MAT_KHAU@db/xime"},
    "jwt": {"secret": "KHOA-KY-JWT-BI-MAT"},
})
print("  repr(config) =", repr(cfg)[:200])
print("  f-string     =", f"{cfg}"[:200])
leak = "SIEU_MAT_KHAU" in repr(cfg) and "KHOA-KY-JWT-BI-MAT" in repr(cfg)
print("  =>", "RÒ: một dòng log/exception in config là lộ toàn bộ secret" if leak else "không rò")

print(); print("="*72); print("PoC 10 - XIME_ENV có bị lợi dụng để đọc file ngoài resources?"); print("="*72)
tmp = tempfile.mkdtemp()
res = os.path.join(tmp, "resources"); os.makedirs(res)
open(os.path.join(res,"application.yml"),"w").write("server:\n  port: 8080\n")
outside = os.path.join(tmp, "application-NGOAI.yml")
open(outside,"w").write("server:\n  port: 1\nbi_mat: DA_DOC_FILE_NGOAI_RESOURCES\n")
loader = YamlConfigLoader(res)
data = loader.load(env="../NGOAI")
print("  XIME_ENV='../NGOAI' -> config nạp được:", data)
print("  =>", "THỦNG: nạp file YAML ngoài thư mục resources" if "bi_mat" in data else "không nạp được")

print(); print("="*72); print("PoC 11 - file profile thiếu thì im lặng hay báo lỗi?"); print("="*72)
d2 = loader.load(env="production")
print("  XIME_ENV='production' (không có application-production.yml) ->", d2)
print("  => im lặng dùng config gốc, KHÔNG có cảnh báo nào")
