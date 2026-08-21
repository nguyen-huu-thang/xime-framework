"""`xime init`: cây thư mục sinh ra phải CHẠY ĐƯỢC, không chỉ trông đúng.

⚠⚠ Nhóm cuối file là nhóm quan trọng nhất, và nó đã trả nợ ngay lần chạy đầu:
bản nháp của trình tạo gọi `configure_routing`, một hàm **không tồn tại**. Nó
trông y hệt một hàm hợp lệ; chỉ lần khởi động thật mới nói. Đúng khuôn 0.7.0 -
ba lỗi mức Cao của bản đó đều nằm ở **chỗ nối**, và 1427 test cũ không bắt được
vì test luôn đi đường tắt mà người dùng thật không có.

⭐⭐ Và nó dạy thêm một bài KHÔNG có trong kế hoạch: **phép đo đầu tiên của tôi
cũng sai, và nó đẻ ra một chẩn đoán hợp lý nhưng không đúng.**

Sau khi sửa `configure_routing`, tôi liệt kê route bằng `adapter.build_app(app)`
và thấy `/ping` vắng mặt - rồi kết luận *"`configure_controllers` phải nhận
module chứ không nhận package"*. Kết luận đó **sai**: `build_app()` không chạy
`lifespan`, mà route được đăng ký **chính trong lifespan**. "Không có route" là
triệu chứng của **công cụ đo**, không phải của code sinh ra.

📌 Cái sai thật nằm ở chỗ tôi **đổi hai biến cùng lúc** (dạng module + cách đo)
rồi gán công cho biến sai. Đối chứng bắt được: gỡ bản "sửa" đó ra thì **không
test nào đỏ**, vì nó chưa bao giờ sửa gì cả.
"""

from __future__ import annotations

import ast
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import yaml

from xime.cli._init import build_plan, module_name, validate_name, write
from xime.cli._main import main


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _make(tmp_path: Path, name: str = "demo-app") -> Path:
    root = tmp_path / name
    write(build_plan(root, name, "0.8.0"))
    return root


class TestTheName:
    @pytest.mark.parametrize("name", ["demo", "demo-app", "a", "don-hang-2"])
    def test_accepted(self, name: str) -> None:
        assert validate_name(name) is None

    @pytest.mark.parametrize("name", ["Demo", "2demo", "demo_app", "demo app", "", "-x"])
    def test_refused(self, name: str) -> None:
        assert validate_name(name) is not None

    def test_a_dash_becomes_an_underscore_in_the_module(self) -> None:
        """Dấu gạch hợp lệ trong tên gói, không hợp lệ trong tên module."""
        assert module_name("don-hang-noi-bo") == "don_hang_noi_bo"


class TestThePlan:
    def test_it_lists_what_it_will_write_before_writing(self, tmp_path: Path) -> None:
        """Dựng trước, ghi sau - không để lại một cây dở dang khi có gì đó hỏng
        giữa chừng."""
        plan = build_plan(tmp_path / "x", "demo", "0.8.0")
        assert "main.py" in plan.files
        assert "resources/application.yml" in plan.files
        assert "resources/application.yml.example" in plan.files
        assert not (tmp_path / "x").exists()

    def test_the_module_package_follows_the_project_name(self, tmp_path: Path) -> None:
        plan = build_plan(tmp_path / "x", "don-hang", "0.8.0")
        assert "don_hang/api/controllers.py" in plan.files

    def test_existing_files_are_reported(self, tmp_path: Path) -> None:
        root = _make(tmp_path)
        plan = build_plan(root, "demo-app", "0.8.0")
        assert "main.py" in plan.existing()


class TestTheGeneratedConfig:
    def test_both_files_are_written(self, tmp_path: Path) -> None:
        root = _make(tmp_path)
        assert (root / "resources/application.yml").exists()
        assert (root / "resources/application.yml.example").exists()

    def test_gitignore_keeps_the_real_one_out_and_the_example_in(
        self, tmp_path: Path
    ) -> None:
        """⭐ Hai file, hai vai - và `.gitignore` là chỗ hai vai đó thành thật."""
        body = (_make(tmp_path) / ".gitignore").read_text(encoding="utf-8")
        assert "resources/application.yml" in body
        assert "!resources/application.yml.example" in body

    def test_the_project_name_reaches_the_store_path(self, tmp_path: Path) -> None:
        loaded = yaml.safe_load(
            (_make(tmp_path) / "resources/application.yml").read_text(encoding="utf-8")
        )
        assert loaded["lmdb"]["path"] == "/dev/shm/demo-app-store"


class TestRefusingToOverwrite:
    def test_a_second_init_is_refused(self, tmp_path: Path, capsys) -> None:
        """⚠ Ghi đè một `application.yml` đang chạy là xoá cấu hình thật của một
        deployment, và không có đường lui."""
        root = _make(tmp_path)

        code = main(["init", "demo-app", "--dir", str(root)])

        assert code == 1
        assert "Refusing To Overwrite" in capsys.readouterr().out

    def test_force_goes_through(self, tmp_path: Path, capsys) -> None:
        root = _make(tmp_path)
        (root / "main.py").write_text("# đã sửa tay\n", encoding="utf-8")

        code = main(["init", "demo-app", "--dir", str(root), "--force"])

        assert code == 0
        assert "Entry point" in (root / "main.py").read_text(encoding="utf-8")
        capsys.readouterr()

    def test_a_bad_name_stops_before_touching_the_disk(
        self, tmp_path: Path, capsys
    ) -> None:
        code = main(["init", "Demo_App", "--dir", str(tmp_path / "x")])

        assert code == 2
        assert not (tmp_path / "x").exists()
        assert "Invalid Project Name" in capsys.readouterr().out


class TestTheGeneratedMainHasTheRightShape:
    """⚠ Nhóm này bịt một lỗ hổng mà **test khởi động thật cũng không thấy**.

    Đặt `app.use(...)` vào trong `if __name__ == "__main__":` chạy hoàn hảo với
    MỘT tiến trình - `python main.py` kích hoạt khối đó. Nó chỉ hỏng khi ai đó
    thêm `share_load()`: tiến trình con chạy lại file này dưới tên `__mp_main__`
    nên khối `if` **không kích hoạt**, và con lên với **không adapter nào, DI
    rỗng**, im lặng.

    Đối chứng tìm ra: chuyển `use()` vào trong khối `if` thì không test nào đỏ.
    """

    def _main_ast(self, tmp_path: Path) -> ast.Module:
        source = (_make(tmp_path) / "main.py").read_text(encoding="utf-8")
        return ast.parse(source)

    def _module_level_calls(self, tree: ast.Module) -> set[str]:
        names: set[str] = set()
        for statement in tree.body:
            if isinstance(statement, ast.If):
                continue  # khối `if __name__` không chạy ở tiến trình con
            for node in ast.walk(statement):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    names.add(node.func.attr)
        return names

    def test_use_and_add_config_run_at_module_level(self, tmp_path: Path) -> None:
        calls = self._module_level_calls(self._main_ast(tmp_path))
        assert "use" in calls
        assert "add_config" in calls

    def test_only_run_lives_inside_the_main_guard(self, tmp_path: Path) -> None:
        """Vế thứ hai: cách "sửa" bằng cách đưa TẤT CẢ ra mức module cũng qua
        được test trên, và lúc đó `run()` chạy ngay khi ai đó `import main`."""
        guards = [s for s in self._main_ast(tmp_path).body if isinstance(s, ast.If)]
        assert len(guards) == 1

        inside: set[str] = set()
        for node in ast.walk(guards[0]):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                inside.add(node.func.attr)
        assert inside == {"run"}

    def test_app_is_a_module_level_name(self, tmp_path: Path) -> None:
        """`share_load()` đòi `app` là biến mức module của `__main__` - tiến
        trình con đi tìm nó ở đó để dựng lại ứng dụng."""
        assigned = {
            target.id
            for statement in self._main_ast(tmp_path).body
            if isinstance(statement, ast.Assign)
            for target in statement.targets
            if isinstance(target, ast.Name)
        }
        assert "app" in assigned


class TestTheGeneratedProjectPassesTheFrameworksOwnChecks:
    """Trình tạo và hai lệnh kiểm phải nói cùng một thứ tiếng.

    Nếu framework tự sinh ra một dự án mà chính nó chê thì một trong hai cái
    đang sai, và người dùng mới là người phát hiện ra.
    """

    def test_check_config(self, tmp_path: Path, capsys) -> None:
        root = _make(tmp_path)
        code = main(["check", "config", "--file", str(root / "resources/application.yml")])
        capsys.readouterr()
        assert code == 0

    def test_check_module_level(self, tmp_path: Path, capsys) -> None:
        root = _make(tmp_path)
        code = main(["check", "module-level", "--root", str(root), "--main", str(root / "main.py")])
        capsys.readouterr()
        assert code == 0


class TestTheGeneratedProjectRunsEXACTLYAsShipped:
    """⛔⭐ Đo dự án **đúng như trình tạo xuất ra**, không thêm một dòng nào.

    Nhóm ngay dưới (`...ActuallyRuns`) **ghi thêm một khối `server:`** vào
    `application.yml` trước khi chạy, để ghim một cổng trống. Nó chứng minh
    được việc nối dây, và **mù hoàn toàn** với câu hỏi *"file trình tạo vừa
    xuất ra có chạy được không"* - vì nó sửa chính cái file đang cần đo.

    Nó đã mù thật: 0.8 làm rơi mặc định cổng của khoá phẳng, nên
    `xime init x && cd x && python main.py` chết ngay lúc khởi động với
    `Web Endpoint Without A Port`, trong khi cả 100 test của giai đoạn 8 vẫn
    xanh. Bản vá nằm ở `_FLAT_DEFAULT_PORTS` trong `core/bootstrap/_processes.py`.

    ⭐ Hai test dưới đo hai thứ khác nhau, không thay nhau được:
    cái đầu **tất định** (đọc đúng file đã sinh, ra đúng con số), cái sau
    **chạy tiến trình thật** nhưng chỉ khẳng định được *"không chết lúc khởi
    động"* - vì cổng 8080 của máy chạy test có thể đang bận, và một lỗi bind
    thì không phải thứ nhóm này canh.
    """

    def test_the_shipped_yaml_resolves_to_the_framework_default_port(
        self, tmp_path: Path
    ) -> None:
        from xime.core.bootstrap._processes import build_topology
        from xime.core.config.runtime import RuntimeConfig

        root = _make(tmp_path)
        raw = yaml.safe_load(
            (root / "resources/application.yml").read_text(encoding="utf-8")
        )
        runtime = RuntimeConfig.from_dict(raw or {})
        topology = build_topology(
            runtime.get, [("web", "default")], share_load=False
        )
        spec = topology.blocks[0].endpoints[("web", "default")]
        assert spec.port == 8080, (
            "file application.yml do trình tạo xuất ra phải phân giải được ra "
            "cổng mặc định của framework; khối `server:` cố ý nằm ở dạng chú "
            "thích vì cổng là thứ framework mặc định ĐƯỢC."
        )

    def test_the_shipped_project_does_not_die_at_startup(self, tmp_path: Path) -> None:
        root = _make(tmp_path)
        process = subprocess.Popen(
            [sys.executable, "-u", "main.py"],
            cwd=str(root),
            env=dict(os.environ, PYTHONPATH=str(root)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            time.sleep(6.0)
            alive_or_bind_error = process.poll()
        finally:
            process.terminate()
            output = process.communicate(timeout=30)[0]

        # Cố ý KHÔNG đòi "phục vụ được": cổng 8080 có thể đang bận trên máy
        # chạy test, và một lỗi bind là chuyện của môi trường. Thứ canh ở đây
        # là lỗi CẤU HÌNH - nó xảy ra trước khi chạm tới mạng.
        assert "Web Endpoint Without A Port" not in output, (
            "dự án vừa sinh ra chết lúc khởi động vì thiếu cổng:\n" + output[-2000:]
        )
        assert "StartupException" not in output, (
            "dự án vừa sinh ra chết lúc khởi động:\n" + output[-2000:]
        )
        del alive_or_bind_error


class TestTheGeneratedProjectActuallyRuns:
    """⭐⭐ Tiến trình THẬT, cổng thật, một lời gọi HTTP thật.

    Mọi test khác ở file này đọc file trên đĩa - nhanh, và **mù với đúng loại
    lỗi mà trình tạo dễ mắc nhất**: code trông hợp lệ, import sai, hoặc nối dây
    thiếu một bước. Hai lỗi thật đã bị nhóm này bắt, xem docstring đầu file.
    """

    def test_it_serves_the_sample_route(self, tmp_path: Path) -> None:
        root = _make(tmp_path)
        port = _free_port()
        with (root / "resources/application.yml").open("a", encoding="utf-8") as handle:
            handle.write(f"\nserver:\n  host: 127.0.0.1\n  port: {port}\n")

        process = subprocess.Popen(
            [sys.executable, "-u", "main.py"],
            cwd=str(root),
            env=dict(os.environ, PYTHONPATH=str(root)),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        body: str | None = None
        try:
            deadline = time.monotonic() + 40.0
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/ping", timeout=1
                    ) as response:
                        body = response.read().decode()
                        break
                except (urllib.error.URLError, OSError):
                    time.sleep(0.4)
        finally:
            process.terminate()
            output = process.communicate(timeout=30)[0]

        assert body is not None, (
            "dự án vừa sinh ra không phục vụ được route mẫu của chính nó:\n"
            + output[-2000:]
        )
        assert "ok" in body
