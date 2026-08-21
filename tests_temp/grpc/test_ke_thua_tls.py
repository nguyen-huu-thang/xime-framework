"""gRPC kế thừa `grpc.tls` khi ô cấu hình không khai - y như web kế thừa `server.ssl`.

Lỗ hổng do **chính 0.8 sinh ra**: trước 0.8 chỉ có khoá phẳng, và đường phẳng chép
`tls` vào ô (`_FLAT_SOURCES`), nên nó luôn đúng. Người di trú sang `process:` theo
đúng lời tài liệu thì mất mTLS, và dấu hiệu duy nhất là một dòng WARNING lẫn trong
log khởi động. Báo từ `Base Platform/data` ngày 2026-08-21.

⚠ Test ở đây đi **thành cặp có hai chiều**, vì tách một hành vi thành hai nhánh thì
kiểm một nhánh không phân biệt được *"đã kế thừa đúng"* với *"đã bật TLS cho tất
cả"*. Cách sửa sai `tls.enabled = True` vô điều kiện cũng qua được nhánh thứ nhất.
"""

from __future__ import annotations

import pytest

from xime.adapters.grpc._adapter import GrpcAdapter, _che_do
from xime.adapters.grpc._config import GrpcServerConfig
from xime.core.bootstrap._processes import build_topology
from xime.core.bootstrap._slot import AdapterSlot
from xime.core.config.runtime import RuntimeConfig

TLS = {"enabled": True, "mutual": True}
DECLARED = [("web", "default"), ("grpc", "default")]


def _tls_cua(raw: dict) -> GrpcServerConfig:
    """Dựng topology thật từ YAML rồi trả về config gRPC adapter sẽ dùng."""
    runtime = RuntimeConfig.from_dict(raw)
    topo = build_topology(runtime.get, DECLARED, share_load=False)
    for block in topo.blocks:
        for (kind, _), spec in block.endpoints.items():
            if kind != "grpc":
                continue
            slot = AdapterSlot(process_id=block.process_id, primary=True, spec=spec)
            return GrpcServerConfig.model_validate(
                {"port": spec.port, **GrpcAdapter.resolve_tls(slot, runtime)}
            )
    raise AssertionError("khong dung duoc endpoint grpc nao")


class TestOKhongKhaiThiKeThua:
    def test_khoi_process_ke_thua_grpc_tls(self):
        """Ca đang hỏng: `process:` không mang `tls`, `grpc.tls` vẫn nằm nguyên."""
        cfg = _tls_cua(
            {
                "process": {
                    "web": {"default": {"port": 8086}},
                    "grpc": {"default": {"host": "0.0.0.0", "port": 9095}},
                },
                "grpc": {"tls": TLS},
            }
        )
        assert cfg.tls.enabled is True
        assert cfg.tls.mutual is True

    def test_khoa_phang_khong_doi_hanh_vi(self):
        """Đối chứng dương: 27/27 app trong workspace dùng khoá phẳng.

        Đường phẳng vốn đã chép `tls` vào ô, nên bản vá phải là **thay đổi rỗng**
        với chúng. Test này đỏ nghĩa là bản vá vừa động vào app đang chạy tốt.
        """
        cfg = _tls_cua({"server": {"port": 8086}, "grpc": {"port": 9095, "tls": TLS}})
        assert cfg.tls.enabled is True
        assert cfg.tls.mutual is True


class TestOKhaiRongThiTonTrong:
    """Nửa còn lại của cặp - và là chỗ phân biệt *kế thừa* với *ép bật*."""

    def test_tls_rong_tuong_minh_van_la_plaintext(self):
        """`tls: {}` là cách khai *"cố ý plaintext"*, đúng khuôn `ssl: {}` của web.

        ⭐ Bỏ test này thì cách sửa sai *"luôn bật TLS"* vẫn xanh hết bảng.
        """
        cfg = _tls_cua(
            {
                "process": {
                    "web": {"default": {"port": 8086}},
                    "grpc": {"default": {"port": 9095, "tls": {}}},
                },
                "grpc": {"tls": TLS},
            }
        )
        assert cfg.tls.enabled is False

    def test_o_ghi_de_duoc_khoi_chung(self):
        """Ô thắng khối chung - nếu không thì `resolve_tls` chỉ là một hằng số."""
        cfg = _tls_cua(
            {
                "process": {
                    "web": {"default": {"port": 8086}},
                    "grpc": {
                        "default": {"port": 9095, "tls": {"enabled": True, "mutual": False}}
                    },
                },
                "grpc": {"tls": TLS},
            }
        )
        assert cfg.tls.enabled is True
        assert cfg.tls.mutual is False, "o phai thang khoi chung, khong phai nguoc lai"


class TestKhongAiNoiGiVeTls:
    def test_may_dev_voi_yml_rong_van_chay(self):
        """Mặc định dễ dãi là **có chủ đích** - máy dev phải chạy với yml rỗng.

        Đối chứng âm thứ hai: nó chặn cách sửa sai *"vắng `grpc.tls` thì bịa ra
        một cái"*.
        """
        cfg = _tls_cua(
            {
                "process": {
                    "web": {"default": {"port": 8086}},
                    "grpc": {"default": {"port": 9095}},
                }
            }
        )
        assert cfg.tls.enabled is False


class TestCheDoNoiRaTrenDongLog:
    """Mốc dương: trạng thái tốt phải để lại dấu vết, không chỉ trạng thái xấu."""

    @pytest.mark.parametrize(
        "enabled,mutual,secure,mong_doi",
        [
            (True, True, True, "mTLS"),
            (True, False, True, "TLS"),
            (False, False, False, "PLAINTEXT"),
        ],
    )
    def test_ba_che_do_phan_biet_duoc(self, enabled, mutual, secure, mong_doi):
        cfg = GrpcServerConfig.model_validate(
            {"port": 1, "tls": {"enabled": enabled, "mutual": mutual}}
        )
        assert _che_do(cfg, secure=secure) == mong_doi
