"""
Test dynamic interface binding (Việc 2, bản 0.6).

Mở rộng `bind`: value có thể là tuple nhiều impl (phần tử đầu = mặc định). Bật/tắt
bằng `dynamic_binding(True/False)` (ánh xạ cờ runtime `xime.di.dynamic-binding`).

  - Cờ TẮT  -> tuple dùng phần tử đầu, hành vi y hệt binding 1-1; impl phụ không dựng.
  - Cờ BẬT  -> consumer nhận proxy trong suốt; `Switcher.use/reset` đổi impl toàn cục.
"""
from typing import Protocol

import pytest

from xime.core.config.binding import BindingConfig
from xime.core.config.runtime import RuntimeConfig
from xime.core.container import XimeContainer
from xime.core.container.switcher import Switcher, SwitcherError
from xime.core.lifecycle.hooks import PostConstruct, PreDestroy
from xime.testing import TestApplication


# ===========================================================================
# Sample interface + implementations
# ===========================================================================

class PaymentGateway(Protocol):
    def charge(self, amount: int) -> str: ...


class StripeGateway:
    def charge(self, amount: int) -> str:
        return f"stripe:{amount}"


class PaypalGateway:
    def charge(self, amount: int) -> str:
        return f"paypal:{amount}"


class MockGateway:
    def charge(self, amount: int) -> str:
        return f"mock:{amount}"


class BadGateway:
    """Thiếu method charge() -> không thỏa Protocol."""
    def refund(self, amount: int) -> str:
        return f"refund:{amount}"


class CheckoutService:
    """Consumer giữ nguyên code cũ: chỉ phụ thuộc Protocol."""
    def __init__(self, gateway: PaymentGateway):
        self.gateway = gateway

    def pay(self, amount: int) -> str:
        return self.gateway.charge(amount)


# ===========================================================================
# Cờ TẮT == hành vi cũ
# ===========================================================================

class TestFlagOff:

    def test_tuple_uses_first_element(self):
        """Cờ tắt: tuple binding dùng phần tử đầu, inject tĩnh như 1-1."""
        c = (
            XimeContainer()
            .register(CheckoutService, StripeGateway)
            .bind({PaymentGateway: (StripeGateway, PaypalGateway, MockGateway)})
            .build()
        )
        svc = c.get(CheckoutService)
        assert isinstance(svc.gateway, StripeGateway)
        assert svc.pay(100) == "stripe:100"

    def test_secondary_impls_not_built(self):
        """Cờ tắt: các impl phụ không được dựng (get() raise KeyError)."""
        c = (
            XimeContainer()
            .register(CheckoutService, StripeGateway)
            .bind({PaymentGateway: (StripeGateway, PaypalGateway, MockGateway)})
            .build()
        )
        # Phần tử đầu được app register như binding cổ điển.
        assert isinstance(c.get(StripeGateway), StripeGateway)
        # Impl phụ không đăng ký -> không dựng.
        with pytest.raises(KeyError):
            c.get(PaypalGateway)
        with pytest.raises(KeyError):
            c.get(MockGateway)

    def test_single_binding_unchanged(self):
        """Binding 1-1 (value là class) vẫn y hệt cũ khi có cờ tắt."""
        c = (
            XimeContainer()
            .register(CheckoutService, StripeGateway)
            .bind({PaymentGateway: StripeGateway})
            .build()
        )
        assert isinstance(c.get(CheckoutService).gateway, StripeGateway)

    def test_one_element_tuple_treated_as_single(self):
        """Tuple một phần tử == binding 1-1, không có gì để switch."""
        c = (
            XimeContainer()
            .register(CheckoutService, StripeGateway)
            .bind({PaymentGateway: (StripeGateway,)})
            .build()
        )
        assert isinstance(c.get(CheckoutService).gateway, StripeGateway)


# ===========================================================================
# Cờ BẬT - proxy + switcher
# ===========================================================================

class TestFlagOn:

    def _container(self) -> XimeContainer:
        return (
            XimeContainer()
            .dynamic_binding(True)
            .register(CheckoutService)
            .bind({PaymentGateway: (StripeGateway, PaypalGateway, MockGateway)})
            .build()
        )

    def test_default_is_first_element(self):
        """Cờ bật: mặc định proxy trỏ phần tử đầu của tuple."""
        c = self._container()
        assert c.get(CheckoutService).pay(50) == "stripe:50"

    def test_consumer_code_unchanged_runs(self):
        """Consumer code cũ (gọi method qua attribute) chạy qua proxy."""
        c = self._container()
        svc = c.get(CheckoutService)
        # Không cần biết về proxy: gọi như impl thật.
        assert svc.pay(7) == "stripe:7"

    def test_switch_affects_all_consumers(self):
        """use() đổi impl toàn cục -> mọi consumer thấy ngay lần gọi kế tiếp."""
        c = self._container()
        switcher = c.get(Switcher)
        svc = c.get(CheckoutService)

        assert svc.pay(1) == "stripe:1"
        switcher.use(PaymentGateway, PaypalGateway)
        assert svc.pay(1) == "paypal:1"
        switcher.use(PaymentGateway, MockGateway)
        assert svc.pay(1) == "mock:1"

    def test_all_impls_are_eager_singletons(self):
        """Cờ bật: mọi impl trong tuple được dựng làm singleton."""
        c = self._container()
        assert isinstance(c.get(StripeGateway), StripeGateway)
        assert isinstance(c.get(PaypalGateway), PaypalGateway)
        assert isinstance(c.get(MockGateway), MockGateway)
        # Proxy forward tới đúng singleton đã dựng.
        c.get(Switcher).use(PaymentGateway, PaypalGateway)
        proxy = c.get(PaymentGateway)
        # Truy cập method qua proxy trả bound method của singleton Paypal.
        assert proxy.charge.__self__ is c.get(PaypalGateway)

    def test_reset_one_interface(self):
        """reset(Interface) đưa một interface về mặc định (phần tử đầu)."""
        c = self._container()
        switcher = c.get(Switcher)
        svc = c.get(CheckoutService)

        switcher.use(PaymentGateway, PaypalGateway)
        assert svc.pay(2) == "paypal:2"
        switcher.reset(PaymentGateway)
        assert svc.pay(2) == "stripe:2"

    def test_reset_all(self):
        """reset() đưa MỌI interface về mặc định."""
        c = self._container()
        switcher = c.get(Switcher)
        svc = c.get(CheckoutService)

        switcher.use(PaymentGateway, MockGateway)
        assert svc.pay(3) == "mock:3"
        switcher.reset()
        assert svc.pay(3) == "stripe:3"

    def test_use_impl_outside_tuple_raises(self):
        """use() với impl ngoài tuple -> SwitcherError."""
        c = self._container()
        with pytest.raises(SwitcherError, match="Invalid dynamic binding switch"):
            c.get(Switcher).use(PaymentGateway, BadGateway)

    def test_use_unknown_interface_raises(self):
        """use() với interface không bind tuple -> SwitcherError."""
        c = self._container()

        class OtherInterface(Protocol):
            def foo(self) -> None: ...

        with pytest.raises(SwitcherError, match="Not a dynamic interface"):
            c.get(Switcher).use(OtherInterface, StripeGateway)


# ===========================================================================
# Switcher khi cờ TẮT - vẫn inject được, nhưng từ chối đổi
# ===========================================================================

class TestSwitcherDisabled:

    def test_switcher_injectable_even_when_off(self):
        """Switcher luôn đăng ký, get() được kể cả khi cờ tắt."""
        c = XimeContainer().build()
        assert isinstance(c.get(Switcher), Switcher)

    def test_use_when_off_raises_clear_error(self):
        """use() khi cờ tắt -> SwitcherError nói rõ cần bật cờ."""
        c = (
            XimeContainer()
            .register(CheckoutService, StripeGateway)
            .bind({PaymentGateway: (StripeGateway, PaypalGateway)})
            .build()
        )
        with pytest.raises(SwitcherError, match="Dynamic binding is disabled"):
            c.get(Switcher).use(PaymentGateway, PaypalGateway)

    def test_reset_when_off_raises(self):
        """reset() khi cờ tắt cũng báo lỗi rõ."""
        c = XimeContainer().build()
        with pytest.raises(SwitcherError, match="Dynamic binding is disabled"):
            c.get(Switcher).reset()


# ===========================================================================
# Validate fail-fast
# ===========================================================================

class TestValidation:

    def test_startup_fails_if_any_tuple_impl_violates_protocol(self):
        """Cờ bật: một impl trong tuple không thỏa Protocol -> startup fail."""
        from xime.core.exception import BindingValidationException

        with pytest.raises(BindingValidationException):
            (
                XimeContainer()
                .dynamic_binding(True)
                .register(CheckoutService)
                .bind({PaymentGateway: (StripeGateway, BadGateway)})
                .build()
            )

    def test_empty_tuple_raises(self):
        """Tuple rỗng -> lỗi cấu hình."""
        with pytest.raises(ValueError, match="empty tuple"):
            (
                XimeContainer()
                .dynamic_binding(True)
                .bind({PaymentGateway: ()})
                .build()
            )

    def test_off_mode_does_not_validate_secondary_impls(self):
        """Cờ tắt: impl phụ không bị validate (chỉ phần tử đầu được dùng)."""
        # BadGateway ở vị trí phụ, cờ tắt -> không build, không validate -> OK.
        c = (
            XimeContainer()
            .register(CheckoutService, StripeGateway)
            .bind({PaymentGateway: (StripeGateway, BadGateway)})
            .build()
        )
        assert c.get(CheckoutService).pay(9) == "stripe:9"


# ===========================================================================
# Proxy KHÔNG bị nhận nhầm là lifecycle component
# ===========================================================================

class StripeWithHooks:
    """Impl có post_construct/pre_destroy để kiểm proxy không forward hook."""
    constructed = 0
    destroyed = 0

    def charge(self, amount: int) -> str:
        return f"stripe:{amount}"

    async def post_construct(self) -> None:
        StripeWithHooks.constructed += 1

    async def pre_destroy(self) -> None:
        StripeWithHooks.destroyed += 1


class TestProxyLifecycleSafety:

    def test_proxy_not_seen_as_lifecycle_component(self):
        """Proxy không được nhận là PostConstruct/PreDestroy (tránh chạy hook 2 lần)."""
        c = (
            XimeContainer()
            .dynamic_binding(True)
            .bind({PaymentGateway: (StripeWithHooks, PaypalGateway)})
            .build()
        )
        proxy = c.get(PaymentGateway)
        # Dù impl hiện hành có hook, proxy KHÔNG được coi là lifecycle component.
        assert not isinstance(proxy, PostConstruct)
        assert not isinstance(proxy, PreDestroy)

    @pytest.mark.asyncio
    async def test_impl_hook_runs_once_not_via_proxy(self):
        """Hook của impl chạy đúng một lần (trên impl), không nhân đôi qua proxy."""
        from xime.core.lifecycle.manager import LifecycleManager

        StripeWithHooks.constructed = 0
        StripeWithHooks.destroyed = 0
        c = (
            XimeContainer()
            .dynamic_binding(True)
            .bind({PaymentGateway: (StripeWithHooks, PaypalGateway)})
            .build()
        )
        instances = c.get_all_in_order()
        manager = LifecycleManager(instances)
        await manager.start()
        await manager.stop()
        # Đúng một impl StripeWithHooks -> hook chạy đúng một lần.
        assert StripeWithHooks.constructed == 1
        assert StripeWithHooks.destroyed == 1


# ===========================================================================
# Đầu-cuối: cờ runtime YAML chảy qua orchestrator (xime.di.dynamic-binding)
# ===========================================================================

def _dynamic_binding() -> BindingConfig:
    b = BindingConfig()
    b.register(CheckoutService)
    b.bind({PaymentGateway: (StripeGateway, PaypalGateway, MockGateway)})
    return b


class TestEndToEndRuntimeFlag:

    @pytest.mark.asyncio
    async def test_flag_on_via_runtime_config_enables_switching(self):
        """Cờ bật trong RuntimeConfig -> orchestrator bật dynamic binding."""
        runtime = RuntimeConfig.from_dict({"xime": {"di": {"dynamic-binding": True}}})
        async with TestApplication(
            binding=_dynamic_binding(), runtime_config=runtime
        ) as app:
            svc = app.get(CheckoutService)
            assert svc.pay(10) == "stripe:10"
            app.get(Switcher).use(PaymentGateway, PaypalGateway)
            assert svc.pay(10) == "paypal:10"

    @pytest.mark.asyncio
    async def test_flag_absent_defaults_to_off(self):
        """Không có cờ -> mặc định tắt -> dùng phần tử đầu, use() báo lỗi."""
        runtime = RuntimeConfig.from_dict({})
        binding = _dynamic_binding()
        # Cờ tắt: phần tử đầu được dùng, app phải tự register nó.
        binding.register(StripeGateway)
        async with TestApplication(
            binding=binding, runtime_config=runtime
        ) as app:
            svc = app.get(CheckoutService)
            assert svc.pay(10) == "stripe:10"
            with pytest.raises(SwitcherError, match="Dynamic binding is disabled"):
                app.get(Switcher).use(PaymentGateway, PaypalGateway)
