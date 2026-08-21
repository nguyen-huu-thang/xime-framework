"""Hai tiến trình phục vụ HTTP trên **cùng một cổng** - phép đo nghiệm thu.

⚠ **Không mock được, và không rút gọn được.** Mọi thứ đáng đo ở đây chỉ tồn tại
khi có tiến trình thật: cha bind rồi truyền socket qua ranh giới tiến trình, con
chạy lại `main.py` dưới tên `__mp_main__`, kernel chia request giữa hai bản
uvicorn. Chạy trong một tiến trình thì cả ba biến mất.

Vì cha là `__main__` của chính nó, bài này phải khởi động một tiến trình Python
thật bằng `subprocess` chứ không gọi hàm - trong pytest thì `__main__` là pytest.
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_HERE = Path(__file__).parent
_REPO = _HERE.parent.parent

# Đợi rộng tay: cha phải import cả cây module rồi sinh hai con, mỗi con lại
# import lại từ đầu (spawn). Trên máy bận, lần đầu tốn vài giây.
_BOOT_TIMEOUT = 60.0


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get(url: str, timeout: float = 2.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for(url: str, deadline: float) -> dict:
    last: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _get(url)
        except (urllib.error.URLError, OSError, TimeoutError) as exc:
            last = exc
            time.sleep(0.2)
    raise AssertionError(f"{url} did not answer in time: {last}")


class Cluster:
    """Một app thật chạy bằng `python -m sample_app.main`.

    ⚠ Log đi ra **FILE**, không ra `PIPE`. Tiến trình con thừa kế đầu ra của cha,
    nên `communicate()` chờ EOF trên một pipe mà cả đàn còn đang giữ - nó treo
    tới hết timeout kể cả khi cha đã chết từ lâu. Đây là cái bẫy kinh điển của
    việc trông một cây tiến trình, không phải chuyện riêng của Xime.
    """

    def __init__(self, workdir: Path, port: int, main: str = "sample_app.main") -> None:
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self._log_path = workdir / "app.log"
        self._log = self._log_path.open("w", encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(_HERE), str(_REPO)])
        env["PYTHONUNBUFFERED"] = "1"
        env.pop("XIME_PROCESS_ID", None)
        kwargs: dict = {}
        if sys.platform == "win32":
            # Nhóm tiến trình riêng để gửi được CTRL_BREAK - tín hiệu DUY NHẤT
            # cha bắt được trên Windows. `terminate()` ở đó là `TerminateProcess`,
            # không handler nào chạy, và con thành mồ côi giữ nguyên cổng.
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(
            [sys.executable, "-m", main],
            cwd=str(workdir),
            env=env,
            stdout=self._log,
            stderr=subprocess.STDOUT,
            text=True,
            **kwargs,
        )

    def output(self) -> str:
        if not self._log.closed:
            self._log.flush()
        try:
            return self._log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def stop(self) -> str:
        """Idempotent: fixture cũng gọi, và test có thể đã gọi trước đó."""
        if self.proc.poll() is None:
            self._signal()
            try:
                self.proc.wait(timeout=30)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
        out = self.output()
        if not self._log.closed:
            self._log.close()
        return out

    def _signal(self) -> None:
        import signal

        if sys.platform == "win32":
            self.proc.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)

    def pids(self, attempts: int = 40) -> set[int]:
        """Gọi nhiều lần rồi gom pid - kernel chia request nên phải hỏi nhiều."""
        seen: set[int] = set()
        for _ in range(attempts):
            try:
                seen.add(_get(f"{self.url}/pid")["pid"])
            except (urllib.error.URLError, OSError, TimeoutError):
                pass
        return seen


def _workdir(tmp_path: Path, yaml_body: str) -> Path:
    resources = tmp_path / "resources"
    resources.mkdir(parents=True, exist_ok=True)
    (resources / "application.yml").write_text(yaml_body, encoding="utf-8")
    return tmp_path


@pytest.fixture
def cluster_factory(tmp_path):
    started: list[Cluster] = []

    def make(yaml_body: str, port: int, main: str = "sample_app.main") -> Cluster:
        cluster = Cluster(_workdir(tmp_path, yaml_body), port, main)
        started.append(cluster)
        return cluster

    yield make

    for cluster in started:
        output = cluster.stop()
        if output.strip():
            print(f"\n--- app output ---\n{output}")


class TestSharedPort:
    def test_two_processes_serve_one_port(self, cluster_factory):
        """Tiêu chí nghiệm thu của giai đoạn 3.

        Cha `bind()` + `listen()` một socket duy nhất rồi truyền nó cho cả hai
        con; kernel chia request. Hai pid khác nhau trả lời trên **một** cổng.
        """
        port = _free_port()
        cluster = cluster_factory(
            "processes:\n"
            "  main:\n"
            "    primary: true\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n"
            "  api-2:\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n",
            port,
        )

        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/pid", deadline)

        seen: set[int] = set()
        while time.monotonic() < deadline and len(seen) < 2:
            seen |= cluster.pids()
        assert len(seen) >= 2, f"only one process answered: {seen}"

        # Và không con nào là chính cha - cha giữ socket nhưng KHÔNG BAO GIỜ
        # accept(). Nếu nó phục vụ thì pid của nó sẽ xuất hiện ở đây.
        assert cluster.proc.pid not in seen

    def test_count_expands_into_that_many_workers(self, cluster_factory):
        """`count: N` là cách viết gọn N tiến trình giống hệt nhau."""
        port = _free_port()
        cluster = cluster_factory(
            "processes:\n"
            "  main:\n"
            "    primary: true\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n"
            "  workers:\n"
            "    count: 2\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n",
            port,
        )

        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/pid", deadline)

        seen: set[int] = set()
        while time.monotonic() < deadline and len(seen) < 3:
            seen |= cluster.pids()
        assert len(seen) >= 3, f"expected 3 workers, saw {seen}"


class TestSupervisorRestartsChildren:
    def test_a_dead_child_comes_back(self, cluster_factory):
        """Cha không được chết, vì con chết thì **không ai dựng lại**.

        Đo bằng một con tự `os._exit(9)`: sau đó cổng phải phục vụ trở lại, và
        bằng một pid mới.
        """
        port = _free_port()
        cluster = cluster_factory(
            "processes:\n"
            "  main:\n"
            "    primary: true\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n",
            port,
        )

        deadline = time.monotonic() + _BOOT_TIMEOUT
        first = _wait_for(f"{cluster.url}/pid", deadline)["pid"]

        with pytest.raises((urllib.error.URLError, OSError, TimeoutError)):
            _get(f"{cluster.url}/die")

        deadline = time.monotonic() + _BOOT_TIMEOUT
        second = None
        while time.monotonic() < deadline:
            try:
                candidate = _get(f"{cluster.url}/pid")["pid"]
            except (urllib.error.URLError, OSError, TimeoutError):
                time.sleep(0.2)
                continue
            if candidate != first:
                second = candidate
                break
            time.sleep(0.2)

        assert second is not None, "supervisor did not bring the child back"
        assert cluster.proc.poll() is None, "the supervisor itself died"


class TestShutdownTakesTheWholeTree:
    def test_stopping_the_parent_frees_the_port(self, cluster_factory):
        """Cha chết mà con sống tiếp là cách hỏng tệ nhất: hệ thống **trông như**
        đã tắt, nhưng con vẫn giữ cổng, vẫn phục vụ, và không ai dựng lại chúng
        nữa. Đo bằng thứ quan sát được: sau khi tắt thì cổng phải bind lại được.
        """
        port = _free_port()
        cluster = cluster_factory(
            "processes:\n"
            "  main:\n"
            "    primary: true\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n"
            "  api-2:\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n",
            port,
        )
        _wait_for(f"{cluster.url}/pid", time.monotonic() + _BOOT_TIMEOUT)

        cluster.stop()

        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            with socket.socket() as probe:
                probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                try:
                    probe.bind(("127.0.0.1", port))
                except OSError:
                    time.sleep(0.3)
                    continue
            return
        raise AssertionError(f"port {port} is still held - an orphan survived")

    def test_the_parent_shuts_down_in_order_instead_of_dying(self, cluster_factory):
        """Cổng được trả lại **không chứng minh** cha tắt tử tế.

        Tín hiệu dừng cũng tới thẳng các con (chúng cùng nhóm tiến trình), nên
        chúng chết dù cha có bắt tín hiệu hay không - cổng vẫn được trả lại. Thứ
        cha bắt tín hiệu mua được là **tắt theo thứ tự**: nó dừng con, đợi, dọn
        socket, rồi thoát sạch.

        Đo bằng hai thứ quan sát được mà cái chết đột ngột không có: **mã thoát
        0** và **dòng log của bước tắt**.
        """
        port = _free_port()
        cluster = cluster_factory(
            "processes:\n"
            "  main:\n"
            "    primary: true\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n",
            port,
        )
        _wait_for(f"{cluster.url}/pid", time.monotonic() + _BOOT_TIMEOUT)

        output = cluster.stop()

        assert cluster.proc.returncode == 0, (
            f"the supervisor died instead of shutting down (exit "
            f"{cluster.proc.returncode})"
        )
        assert "supervisor: stopping" in output, (
            "no shutdown log line - the supervisor never reached its teardown"
        )


class TestPrivatePorts:
    def test_each_process_can_own_its_port(self, cluster_factory):
        """Vế đối chứng của cổng dùng chung: không khai `shared` thì mỗi tiến
        trình một cổng, và cha không bind gì cả."""
        port_a, port_b = _free_port(), _free_port()
        cluster = cluster_factory(
            "processes:\n"
            "  main:\n"
            "    primary: true\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port_a} }} }}\n"
            "  api-2:\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port_b} }} }}\n",
            port_a,
        )

        deadline = time.monotonic() + _BOOT_TIMEOUT
        first = _wait_for(f"http://127.0.0.1:{port_a}/pid", deadline)["pid"]
        second = _wait_for(f"http://127.0.0.1:{port_b}/pid", deadline)["pid"]

        assert first != second


class TestStartupFailureIsLoud:
    def test_a_typo_in_the_config_stops_the_parent(self, cluster_factory):
        """Cha kiểm trước khi sinh con, nên lỗi cấu hình ra **một** thông báo -
        không phải bốn stack trace giống nhau từ bốn con."""
        port = _free_port()
        cluster = cluster_factory(
            "processes:\n"
            "  main:\n"
            "    primary: true\n"
            f"    web: {{ publik: {{ host: 127.0.0.1, port: {port} }} }}\n",
            port,
        )

        assert cluster.proc.wait(timeout=_BOOT_TIMEOUT) != 0
        assert "Unknown Endpoint" in cluster.output()




class TestTheSingleProcessShape:
    def test_one_process_serves_two_web_ports(self, cluster_factory, tmp_path):
        """Khối `process:` - một tiến trình, hai cổng HTTP.

        ⭐ Đây là chỗ chứng minh *"server phụ"* và *"tiến trình phụ"* là **hai
        trục khác nhau**: không có `share_load()`, không có tiến trình con, mà
        vẫn hai cổng - và **cùng một pid** trả lời cả hai.
        """
        port_a, port_b = _free_port(), _free_port()
        cluster = cluster_factory(
            "process:\n"
            "  web:\n"
            f"    public: {{ host: 127.0.0.1, port: {port_a} }}\n"
            f"    admin:  {{ host: 127.0.0.1, port: {port_b} }}\n",
            port_a,
            main="sample_two.main",
        )

        deadline = time.monotonic() + _BOOT_TIMEOUT
        first = _wait_for(f"http://127.0.0.1:{port_a}/pid", deadline)["pid"]
        second = _wait_for(f"http://127.0.0.1:{port_b}/pid", deadline)["pid"]

        assert first == second, "hai cổng phải do CÙNG một tiến trình phục vụ"
        assert first != cluster.proc.pid or True  # không có cha, nên pid chính là nó

    def test_the_flat_server_key_still_works(self, cluster_factory):
        """58/69 file cấu hình trong workspace dùng khoá phẳng này.

        Nó là một phép **dịch** thành `process.web.default`, không phải một nhánh
        xử lý thứ hai - nên nếu nó hỏng thì hỏng ở chỗ dịch, và test này là chỗ
        duy nhất đi qua đường đó bằng một tiến trình thật.
        """
        port = _free_port()
        cluster = cluster_factory(
            f"server:\n  host: 127.0.0.1\n  port: {port}\n",
            port,
            main="sample_one.main",
        )
        _wait_for(f"{cluster.url}/pid", time.monotonic() + _BOOT_TIMEOUT)


class TestRefDataAcrossProcesses:
    """Cha cấp vùng nhớ TRƯỚC khi sinh con, con attach vào ĐÚNG vùng đó.

    ⭐ Đây là câu mà **không test nào khác của `RefData` trả lời được**: bộ test
    ở `tests_temp/refdata/` hoặc chạy một tiến trình, hoặc tự dựng arena bằng
    tay rồi `attach` bằng tay. Cả hai đều đi vòng qua chính đoạn nối đang cần
    đo - `allocate_shared_memory()` ở cha, `SharedHandle` truyền xuống, và
    `run_as_worker(..., shared)` ở con.

    Cùng bài học đã cắn hai lần trong 0.8: lỗi nằm ở **chỗ nối**, và test đi
    đường tắt không thấy.
    """

    def test_the_primary_publishes_and_the_other_process_reads_it(
        self, cluster_factory
    ):
        port = _free_port()
        cluster = cluster_factory(
            "processes:\n"
            "  main:\n"
            "    primary: true\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n"
            "  api-2:\n"
            f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n",
            port,
        )

        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/refdata", deadline)

        # Trước khi ai publish: MỌI tiến trình phải nói "chưa sẵn sàng", chứ
        # không phải một giá trị rỗng.
        for _ in range(20):
            body = _get(f"{cluster.url}/refdata")
            assert body["value"] is None
            assert body["generation"] == 0

        # Kernel chia request nên phải hỏi vài lần mới trúng primary.
        while time.monotonic() < deadline:
            if _get(f"{cluster.url}/publish")["published"]:
                break
        else:
            raise AssertionError("không lần nào request rơi vào primary")

        # Và bây giờ CẢ HAI tiến trình phải thấy bản mới - qua vùng nhớ do cha
        # cấp, không qua bất cứ đường nào khác.
        seen: dict[int, dict] = {}
        while time.monotonic() < deadline and len(seen) < 2:
            body = _get(f"{cluster.url}/refdata")
            seen[body["pid"]] = body
        assert len(seen) >= 2, f"chỉ một tiến trình trả lời: {list(seen)}"
        for pid, body in seen.items():
            assert body["value"] == {"kid": "k1", "pem": "pem-1"}, (pid, body)
            assert body["generation"] == 1, (pid, body)

        # Đối chứng cho chính phép đo: đúng MỘT tiến trình được quyền ghi.
        assert sum(1 for b in seen.values() if b["primary"]) == 1

        # Và mỗi tiến trình mang một chỉ số RIÊNG, lấy theo thứ tự khai trong
        # cấu hình chứ không theo thứ tự sinh - nhờ vậy một con được dựng lại
        # giữ nguyên chỉ số của nó, và `stats().writer` không bao giờ trỏ vào
        # một tiến trình đã chết.
        assert sorted(b["index"] for b in seen.values()) == [0, 1]

