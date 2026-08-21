"""`/healthz` và `/readyz` trả lời HAI câu, và gộp chúng là một ca của luật 03.

| | Câu hỏi | Ai đọc | Đỏ thì họ làm gì |
|---|---|---|---|
| `/healthz` | *"tiến trình này còn dùng được không"* | systemd, k8s | **restart** |
| `/readyz` | *"nhận request mới được không"* | load balancer | **rút khỏi vòng** |

Test đi thành cặp ở đúng chỗ hai câu trả lời khác nhau: **một** adapter hỏng
trong khi cái khác còn phục vụ.
"""

from __future__ import annotations

from xime.core.bootstrap._health import (
    ISOLATED,
    SERVING,
    STANDBY,
    AdapterHealth,
    HealthReport,
)


def _report(*states: str, primary: bool = True) -> HealthReport:
    return HealthReport(
        primary=primary,
        adapters=tuple(
            AdapterHealth(adapter_id=f"a{i}", kind="web", state=s)
            for i, s in enumerate(states)
        ),
    )


class TestOneBrokenAdapterSplitsTheTwoAnswers:
    """⭐ Ca cả hai câu phải trả lời KHÁC nhau - và là lý do không gộp chúng."""

    def test_the_load_balancer_pulls_it_out(self) -> None:
        assert _report(SERVING, ISOLATED).ready is False

    def test_but_systemd_does_not_kill_it(self) -> None:
        # Giết một tiến trình phục vụ được một phần là đổi *hỏng một phần* lấy
        # *hỏng toàn phần* - mất luôn log và khả năng gỡ lỗi.
        assert _report(SERVING, ISOLATED).alive is True


class TestEverythingBrokenIsRedOnBoth:
    def test_ready_is_false(self) -> None:
        assert _report(ISOLATED, ISOLATED).ready is False

    def test_alive_is_false(self) -> None:
        assert _report(ISOLATED, ISOLATED).alive is False


class TestEverythingHealthyIsGreenOnBoth:
    def test_ready_is_true(self) -> None:
        assert _report(SERVING, SERVING).ready is True

    def test_alive_is_true(self) -> None:
        assert _report(SERVING, SERVING).alive is True


class TestAStandbySingletonIsNotAFault:
    """⭐ Chốt 2026-08-19: `/readyz` của con phụ **VẪN XANH** khi cụm thiếu
    primary.

    Con phụ vẫn **nhận request được**; thứ cụm mất là **job nền**. Trả lời ngược
    lại thì LB rút hết con và cụm chết hoàn toàn vì một job nền không chạy -
    đúng ngược nguyên tắc *"mất job nền còn hơn mất khả năng phục vụ"*.
    """

    def test_a_waiting_singleton_keeps_readyz_green(self) -> None:
        assert _report(SERVING, STANDBY, primary=False).ready is True

    def test_and_healthz_green_too(self) -> None:
        assert _report(SERVING, STANDBY, primary=False).alive is True

    def test_a_process_that_only_holds_a_standby_is_still_alive(self) -> None:
        """Một con phụ của app chỉ có scheduler: không phục vụ gì, nhưng cũng
        không hỏng gì, và restart nó không làm ai khá hơn."""
        assert _report(STANDBY, primary=False).alive is True

    def test_the_missing_primary_is_still_visible(self) -> None:
        # Thông tin *"cụm đang không có primary"* không được biến mất chỉ vì
        # `ready` xanh - nó chỉ đi bằng một trường khác.
        assert _report(SERVING, STANDBY, primary=False).primary is False


class TestNoAdapterAtAll:
    def test_a_process_with_no_adapter_is_alive(self) -> None:
        # Không có gì để hỏng thì không có gì hỏng. Ca 2 và ca 3 của năm ca
        # supervisor sống ở đây.
        assert _report().alive is True

    def test_and_ready(self) -> None:
        assert _report().ready is True


class TestTheDictShape:
    def test_it_carries_both_answers_and_the_adapters(self) -> None:
        data = _report(SERVING, ISOLATED).as_dict()
        assert data["alive"] is True
        assert data["ready"] is False
        assert data["primary"] is True
        assert [a["state"] for a in data["adapters"]] == [SERVING, ISOLATED]  # type: ignore[index,union-attr]

    def test_it_leaks_nothing_sensitive(self) -> None:
        """Hai đường dẫn cố ý **không xác thực** - chúng phải trả lời được khi
        mọi thứ khác đã hỏng. Cái giá là thân phản hồi không được mang gì."""
        data = _report(SERVING).as_dict()
        assert set(data) == {"alive", "ready", "primary", "adapters"}
        assert set(data["adapters"][0]) == {"id", "kind", "state"}  # type: ignore[index]
