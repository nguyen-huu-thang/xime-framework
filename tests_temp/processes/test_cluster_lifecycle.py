"""Cụm thật: `run_once`, thăng cấp primary, watchdog, `/readyz`.

⚠ **Không mock được.** Mọi thứ đáng đo ở đây chỉ tồn tại khi có tiến trình thật:
`waitpid` là sự thật của kernel chứ không phải một cờ, nhịp vỗ chỉ có nghĩa khi
có một event loop thật để chặn, và *"chạy một lần cho cả cụm"* không phát biểu
được trong một tiến trình.

Đây cũng là chỗ duy nhất đo được **đoạn nối**: cha cấp bus và bảng nhịp trước
khi sinh con, con attach đúng vùng đó, và hai bên nói chuyện được. Ba giai đoạn
trước đã dạy cùng một bài học ba lần - lỗi nằm ở chỗ nối, và test đi đường tắt
không thấy.
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

_BOOT_TIMEOUT = 60.0

# Ngưỡng im lặng của watchdog là 10 giây (hằng số của thiết kế), cộng một vòng
# giám sát, cộng thời gian dựng lại con. Đo thật thì phải chờ thật.
_WATCHDOG_TIMEOUT = 45.0


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get(url: str, timeout: float = 2.0) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _try_get(url: str, timeout: float = 2.0) -> dict | None:
    try:
        return _get(url, timeout)
    except Exception:  # noqa: BLE001 - đang đo một cụm đang hỏng
        return None


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
    """Một app thật chạy bằng `python -m sample_cluster.main`."""

    def __init__(self, workdir: Path, port: int) -> None:
        self.port = port
        self.workdir = workdir
        self.url = f"http://127.0.0.1:{port}"
        self._log_path = workdir / "app.log"
        self._log = self._log_path.open("w", encoding="utf-8")
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(_HERE), str(_REPO)])
        env["PYTHONUNBUFFERED"] = "1"
        env.pop("XIME_PROCESS_ID", None)
        kwargs: dict = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "sample_cluster.main"],
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

    def lines_of(self, name: str) -> list[str]:
        path = self.workdir / name
        if not path.exists():
            return []
        return [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln]

    def pids(self, attempts: int = 40) -> set[int]:
        seen: set[int] = set()
        for _ in range(attempts):
            got = _try_get(f"{self.url}/pid", 1.0)
            if got:
                seen.add(got["pid"])
        return seen

    def roles(self, attempts: int = 40) -> dict[bool, dict]:
        """Gom `/readyz` cho tới khi thấy cả primary lẫn con phụ trả lời."""
        out: dict[bool, dict] = {}
        for _ in range(attempts):
            got = _try_get(f"{self.url}/readyz", 1.0)
            if got is not None:
                out[bool(got["primary"])] = got
            if len(out) == 2:
                break
        return out

    def stamps_of(self, name: str) -> list[tuple[int, float]]:
        """Đọc một sổ `<pid> <mốc>` mà app ghi ra."""
        out: list[tuple[int, float]] = []
        for line in self.lines_of(name):
            pid, _, stamp = line.partition(" ")
            out.append((int(pid), float(stamp) if stamp else 0.0))
        return out

    def primary_pid(self, deadline: float) -> int:
        """Pid của primary, đọc từ dấu vết adapter đơn nhất để lại.

        Không hỏi qua HTTP vì kernel chia request: hỏi *"ai là primary"* rồi giết
        ở lời gọi thứ hai là một cuộc đua, và phép đo sẽ giết nhầm người rồi vẫn
        xanh - vì nó chỉ kiểm rằng *có ai đó* đã chết.
        """
        while time.monotonic() < deadline:
            lines = self.lines_of("singleton_started.log")
            if lines:
                return int(lines[-1].split()[0])
            time.sleep(0.2)
        raise AssertionError("không tiến trình nào khởi động adapter đơn nhất")

    def kill_pid(self, pid: int, deadline: float) -> None:
        """Giết ĐÚNG một tiến trình. Một lời gọi vừa chọn vừa hành động."""
        while time.monotonic() < deadline:
            got = _try_get(f"{self.url}/die?pid={pid}", 1.0)
            if got is None:
                return  # nó chết giữa lúc trả lời - đúng ý đồ
            if got.get("pid") == pid:
                return
        raise AssertionError(f"không gọi trúng tiến trình {pid}")

    def stop(self) -> str:
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


def _yaml(port: int) -> str:
    return (
        "processes:\n"
        "  main:\n"
        "    primary: true\n"
        f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n"
        "    fragile: { default: {} }\n"
        "    breakable: { default: {} }\n"
        "  api-2:\n"
        f"    web: {{ default: {{ host: 127.0.0.1, port: {port}, shared: true }} }}\n"
        "    breakable: { default: {} }\n"
    )


@pytest.fixture
def cluster(tmp_path):
    port = _free_port()
    resources = tmp_path / "resources"
    resources.mkdir(parents=True, exist_ok=True)
    (resources / "application.yml").write_text(_yaml(port), encoding="utf-8")
    node = Cluster(tmp_path, port)
    try:
        yield node
    finally:
        output = node.stop()
        if output.strip():
            print(f"\n--- app output ---\n{output}")


# ---------------------------------------------------------------------------
# run_once
# ---------------------------------------------------------------------------


class TestRunOnceIsOncePerCluster:
    def test_it_runs_exactly_once_while_post_construct_runs_everywhere(
        self, cluster: Cluster
    ) -> None:
        """⭐ Cặp phép đo này là **cả điểm** của `RunOnce`.

        Trước 0.8 hai loại việc nằm chung `post_construct`, nên trong cụm bốn
        tiến trình thì migration chạy bốn lần và job nhắc email gửi bốn lần.
        Tách ra thì `post_construct` vẫn chạy ở mọi tiến trình (đúng - mọi con
        cần pool DB), còn `run_once` chỉ chạy một lần.
        """
        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/pid", deadline)
        # Đợi cho cả hai con lên - `run_once` xong TRƯỚC khi con thứ hai sinh ra.
        seen: set[int] = set()
        while time.monotonic() < deadline and len(seen) < 2:
            seen |= cluster.pids()

        assert len(cluster.lines_of("run_once.log")) == 1, (
            "run_once chạy nhiều hơn một lần cho cả cụm"
        )
        assert len(cluster.lines_of("post_construct.log")) >= 2, (
            "post_construct phải chạy ở MỌI tiến trình - cắt nó đi là con phụ "
            "dựng DI xong mà không có kết nối nào"
        )

    def test_the_primary_is_the_one_that_ran_it(self, cluster: Cluster) -> None:
        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/pid", deadline)
        while time.monotonic() < deadline and not cluster.lines_of(
            "singleton_started.log"
        ):
            time.sleep(0.2)
        ran_once = [pid for pid, _ in cluster.stamps_of("run_once.log")]
        singleton = [pid for pid, _ in cluster.stamps_of("singleton_started.log")]
        assert ran_once and singleton
        assert ran_once[0] == singleton[0], (
            "run_once và adapter đơn nhất phải ở cùng một tiến trình - cả hai "
            "đều là 'một lần cho cả cụm'"
        )


# ---------------------------------------------------------------------------
# Vai primary nhìn từ ngoài
# ---------------------------------------------------------------------------


class TestTheParentWaitsForRunOnce:
    """⭐⭐ Đây là chỗ `run_once` khác một job *"chạy một lần"* của scheduler.

    Job scheduler nghĩa là *chạy một lần vào một thời điểm*; `run_once` nghĩa là
    **chạy một lần, và mọi thứ khác đợi nó**. Migration xong rồi mới có con thứ
    hai mở kết nối.

    ⚠ Phép đo này chỉ có nghĩa vì `Migration.run_once` **chậm có chủ ý**: nếu nó
    chạy tức thì thì gỡ hẳn bước đợi ra cũng cho kết quả y hệt, và test sẽ xanh
    trên một cụm không còn giữ lời hứa nào.
    """

    def test_no_other_process_builds_its_di_before_run_once_finishes(
        self, cluster: Cluster
    ) -> None:
        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/pid", deadline)
        seen: set[int] = set()
        while time.monotonic() < deadline and len(seen) < 2:
            seen |= cluster.pids()
        assert len(seen) >= 2

        done = cluster.stamps_of("run_once.log")
        assert len(done) == 1
        primary_pid, finished_at = done[0]

        others = [
            (pid, stamp)
            for pid, stamp in cluster.stamps_of("post_construct.log")
            if pid != primary_pid
        ]
        assert others, "chỉ thấy một tiến trình - phép đo không nói được gì"
        early = [(pid, stamp) for pid, stamp in others if stamp < finished_at]
        assert not early, (
            f"tiến trình {early} dựng DI TRƯỚC khi run_once xong ({finished_at}) - "
            "cha không đợi, nên một migration chưa chạy xong đã có người khác "
            "mở kết nối vào cùng database"
        )


class TestTheRoleIsVisible:
    def test_one_process_is_primary_and_the_other_is_not(
        self, cluster: Cluster
    ) -> None:
        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/readyz", deadline)
        roles: dict[bool, dict] = {}
        while time.monotonic() < deadline and len(roles) < 2:
            roles |= cluster.roles()
        assert set(roles) == {True, False}, f"chỉ thấy {sorted(roles)}"

    def test_the_standby_process_stays_green(self, cluster: Cluster) -> None:
        """⭐ Chốt 2026-08-19: `/readyz` của con phụ **VẪN XANH**.

        Nó vẫn nhận request được; thứ cụm mất khi thiếu primary là job nền. Trả
        lời ngược lại thì LB rút hết con và cụm chết hoàn toàn vì một job nền
        không chạy.
        """
        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/readyz", deadline)
        roles: dict[bool, dict] = {}
        while time.monotonic() < deadline and len(roles) < 2:
            roles |= cluster.roles()
        assert roles[False]["ready"] is True
        assert roles[False]["alive"] is True
        # Adapter đơn nhất ở con phụ nằm ở `standby`, và standby KHÔNG phải lỗi.
        states = {a["kind"]: a["state"] for a in roles[False]["adapters"]}
        assert states.get("fragile") == "standby"
        assert states.get("web") == "serving"


# ---------------------------------------------------------------------------
# Thăng cấp
# ---------------------------------------------------------------------------


class TestPromotion:
    def _boot(self, cluster: Cluster) -> tuple[float, dict[bool, dict]]:
        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/readyz", deadline)
        roles: dict[bool, dict] = {}
        while time.monotonic() < deadline and len(roles) < 2:
            roles |= cluster.roles()
        assert set(roles) == {True, False}
        return deadline, roles

    def test_the_survivor_takes_the_role(self, cluster: Cluster) -> None:
        """Primary chết -> cha thăng cấp con còn sống, và con đó khởi động
        adapter đơn nhất."""
        deadline, _roles = self._boot(cluster)
        started_before = len(cluster.lines_of("singleton_started.log"))

        deadline = time.monotonic() + _BOOT_TIMEOUT
        cluster.kill_pid(cluster.primary_pid(deadline), deadline)

        # Con còn sống phải nhận vai VÀ khởi động adapter đơn nhất ở đó.
        deadline = time.monotonic() + _BOOT_TIMEOUT
        while time.monotonic() < deadline:
            if len(cluster.lines_of("singleton_started.log")) > started_before:
                break
            time.sleep(0.2)
        assert len(cluster.lines_of("singleton_started.log")) > started_before, (
            "không ai nhận vai primary sau khi primary chết - cụm mất job nền "
            "vĩnh viễn và không gì báo"
        )

    def test_run_once_is_not_repeated_when_it_already_finished(
        self, cluster: Cluster
    ) -> None:
        """Cha đã nhận tín hiệu *xong*, nên con thăng cấp **không** chạy lại.

        Vế ngược lại (chưa nhận tín hiệu thì chạy lại) là lý do `run_once()`
        phải lặp-lại-được - ràng buộc khai kèm Protocol.
        """
        deadline, _ = self._boot(cluster)
        assert len(cluster.lines_of("run_once.log")) == 1
        started_before = len(cluster.lines_of("singleton_started.log"))

        deadline = time.monotonic() + _BOOT_TIMEOUT
        cluster.kill_pid(cluster.primary_pid(deadline), deadline)

        deadline = time.monotonic() + _BOOT_TIMEOUT
        while time.monotonic() < deadline:
            if len(cluster.lines_of("singleton_started.log")) > started_before:
                break
            time.sleep(0.2)
        assert len(cluster.lines_of("run_once.log")) == 1

    def test_the_restarted_process_does_not_come_back_as_primary(
        self, cluster: Cluster
    ) -> None:
        """⭐⭐ Ca HAI PRIMARY, và nó hỏng hoàn toàn im lặng.

        Cấu hình nói `main: primary: true`. Nếu con đọc vai từ **cấu hình** thì
        `main` chết, cha thăng cấp `api-2`, rồi `main` được dựng lại và quay về
        **vẫn tin mình là primary** - trong khi cha đã trao vai cho người khác.
        Hai tiến trình cùng chạy job nền, không lỗi nào phát ra, và triệu chứng
        duy nhất là mọi việc nền chạy hai lần.

        Nên vai primary phải đến từ **cha** (`SharedHandle.primary`), thứ duy
        nhất biết ai đang giữ nó.

        ⚠ Phép đo là **đếm số lần adapter đơn nhất được khởi động**: đúng thì có
        hai (primary lúc khởi động, rồi người được thăng cấp), sai thì có ba.
        Chỉ hỏi *"có ai đó nhận vai không"* thì bản sai cũng qua được - nó nhận
        vai, chỉ là nhận thừa một người.
        """
        deadline, _ = self._boot(cluster)
        assert len(cluster.lines_of("singleton_started.log")) == 1

        deadline = time.monotonic() + _BOOT_TIMEOUT
        victim = cluster.primary_pid(deadline)
        before = cluster.pids()
        cluster.kill_pid(victim, deadline)

        # Đợi (a) ai đó nhận vai, và (b) tiến trình đã chết được dựng lại và
        # phục vụ trở lại - chỉ khi cả hai xong thì con số mới nói được gì.
        deadline = time.monotonic() + _BOOT_TIMEOUT
        promoted = False
        respawned: set[int] = set()
        while time.monotonic() < deadline:
            if len(cluster.lines_of("singleton_started.log")) >= 2:
                promoted = True
            respawned |= cluster.pids(attempts=10) - before
            if promoted and respawned:
                break
            time.sleep(0.3)
        assert promoted, "không ai nhận vai primary"
        assert respawned, "tiến trình đã chết không được dựng lại"

        # Cho tiến trình vừa dựng lại đủ thời gian để làm điều sai, nếu nó định làm.
        time.sleep(2.0)
        started = cluster.lines_of("singleton_started.log")
        assert len(started) == 2, (
            f"adapter đơn nhất khởi động {len(started)} lần: {started}. Tiến trình "
            "được dựng lại đã quay về với vai primary trong khi cha đã trao vai "
            "cho người khác - hai primary cùng chạy job nền"
        )

    def test_a_failing_start_refuses_the_role_without_dying(
        self, cluster: Cluster
    ) -> None:
        """⭐⭐ Ca 4.4: `start()` hỏng **lúc thăng cấp** thì từ chối vai, KHÔNG sập.

        Sập là mất một tiến trình đang phục vụ người dùng thật vì một cái cert,
        và làm đúng thế ba lần liên tiếp chính là domino.
        """
        deadline, _ = self._boot(cluster)
        # Lấy pid primary TRƯỚC khi cài bẫy: sau khi cài, `/trap` có thể rơi vào
        # bất kỳ con nào, còn file bẫy thì cả cụm dùng chung.
        deadline = time.monotonic() + _BOOT_TIMEOUT
        victim = cluster.primary_pid(deadline)
        _try_get(f"{cluster.url}/trap", 2.0)
        cluster.kill_pid(victim, deadline)

        # Con từ chối vai vẫn PHẢI phục vụ HTTP.
        deadline = time.monotonic() + _BOOT_TIMEOUT
        served = _wait_for(f"{cluster.url}/pid", deadline)
        assert "pid" in served

        # Và cha phải BIẾT. Đợi có nhịp: cha đọc kênh điều khiển mỗi vòng giám
        # sát, nên tin *"tôi không nhận được vai"* tới sau khi con đã trả lời
        # HTTP xong từ lâu.
        deadline = time.monotonic() + _BOOT_TIMEOUT
        while time.monotonic() < deadline:
            if "REFUSED the primary role" in cluster.output():
                break
            time.sleep(0.3)
        assert "REFUSED the primary role" in cluster.output(), (
            "cha phải biết khi một con từ chối vai - không thì cụm mất job nền "
            "trong im lặng"
        )


# ---------------------------------------------------------------------------
# F10: con báo cha những gì
# ---------------------------------------------------------------------------


class TestTheChildReportsToTheParent:
    """Cha nghe được ba cột mốc, và cả ba đi qua **bus**, không qua nhịp watchdog.

    ⚠ Watchdog trả lời *"tôi còn quay không"* - một nhịp đều đặn, một câu duy
    nhất. Bus trả lời *"vừa có chuyện gì xảy ra"* - một sự kiện. Nhồi cái sau vào
    cái trước là bắt một cơ chế trả lời hai câu.
    """

    def test_the_parent_learns_that_each_child_is_serving(
        self, cluster: Cluster
    ) -> None:
        """Tín hiệu *"đã sẵn sàng"* của F10, gửi SAU `start()` và TRƯỚC `serve()`.

        Đợi tới sau `serve()` thì không bao giờ tới - `serve()` chặn suốt vòng
        đời - và cha sẽ không bao giờ biết khi nào sinh con tiếp theo.
        """
        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/pid", deadline)
        seen: set[int] = set()
        while time.monotonic() < deadline and len(seen) < 2:
            seen |= cluster.pids()

        deadline = time.monotonic() + _BOOT_TIMEOUT
        while time.monotonic() < deadline:
            if cluster.output().count("is serving") >= 2:
                break
            time.sleep(0.3)
        assert cluster.output().count("is serving") >= 2, (
            "cha không nghe được con nào báo đã sẵn sàng - nó sẽ không bao giờ "
            "biết khi nào sinh con tiếp theo"
        )

    def test_an_adapter_that_dies_while_serving_is_isolated_and_reported(
        self, cluster: Cluster
    ) -> None:
        """⭐ Ca F10 thứ ba: đã phục vụ rồi mới hỏng.

        Ba điều phải cùng đúng: adapter đó chết **một mình**, tiến trình **vẫn
        sống** (còn `/healthz` thì còn gỡ lỗi được), và cha **biết**.
        """
        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/pid", deadline)
        seen: set[int] = set()
        while time.monotonic() < deadline and len(seen) < 2:
            seen |= cluster.pids()

        _try_get(f"{cluster.url}/break", 2.0)

        deadline = time.monotonic() + _BOOT_TIMEOUT
        while time.monotonic() < deadline:
            if "isolated adapter" in cluster.output():
                break
            time.sleep(0.3)
        assert "isolated adapter" in cluster.output(), (
            "cha không biết một adapter vừa bị cô lập - cụm phục vụ thiếu một "
            "phần và không ai thấy gì"
        )

        # Và tiến trình đó vẫn trả lời: cô lập, không sập.
        assert _wait_for(f"{cluster.url}/pid", time.monotonic() + 10.0)


# ---------------------------------------------------------------------------
# Watchdog
# ---------------------------------------------------------------------------


class TestWatchdogCatchesAHungProcess:
    """⭐ Ca duy nhất `waitpid` mù: tiến trình còn sống, event loop thì không."""

    def test_a_blocked_loop_gets_killed_and_replaced(self, cluster: Cluster) -> None:
        deadline = time.monotonic() + _BOOT_TIMEOUT
        _wait_for(f"{cluster.url}/pid", deadline)
        before: set[int] = set()
        while time.monotonic() < deadline and len(before) < 2:
            before |= cluster.pids()
        assert len(before) >= 2

        # Chặn loop của MỘT con. Nó vẫn sống theo kernel, nên `waitpid` im.
        try:
            urllib.request.urlopen(f"{cluster.url}/block", timeout=1.0)
        except Exception:  # noqa: BLE001 - không bao giờ trả lời, đó là ý đồ
            pass

        deadline = time.monotonic() + _WATCHDOG_TIMEOUT
        while time.monotonic() < deadline:
            if "its event loop is blocked" in cluster.output():
                break
            time.sleep(0.5)
        assert "its event loop is blocked" in cluster.output(), (
            "cha không phát hiện con treo - watchdog là thứ duy nhất nhìn thấy "
            "cách hỏng này"
        )

        # Và cụm phải phục hồi: một pid MỚI trả lời sau đó.
        deadline = time.monotonic() + _BOOT_TIMEOUT
        after: set[int] = set()
        while time.monotonic() < deadline and not (after - before):
            after |= cluster.pids()
        assert after - before, "con bị giết không được dựng lại"
