"""
Test đăng ký DI thủ công:
  - register()  — đăng ký class cụ thể, framework tự inject
  - configure() — config class với factory method (Option B)
"""
from typing import Protocol

import pytest

from xime.core.container import XimeContainer
from xime.core.container.config_loader import ConfigClassError, ConfigClassLoader


# ===========================================================================
# Sample classes — domain layer (bình thường bị loại trừ khỏi auto-scan)
# ===========================================================================

class IdFactory:
    """Domain factory, không có dependency."""
    def generate(self) -> str:
        return "generated-id"


class CredentialFactory:
    """Domain factory, phụ thuộc IdFactory."""
    def __init__(self, id_factory: IdFactory):
        self.id_factory = id_factory

    def create(self) -> dict:
        return {"id": self.id_factory.generate()}


class AuthService:
    """Application service, phụ thuộc CredentialFactory."""
    def __init__(self, factory: CredentialFactory):
        self.factory = factory

    def authenticate(self) -> dict:
        return self.factory.create()


# ===========================================================================
# Sample classes — configure() use cases
# ===========================================================================

class AppConfig:
    """Pre-built config, đăng ký qua register_instance()."""
    secret_key: str = "test-secret"


class Cipher:
    """Tạo ra bởi factory method không có dep."""
    def encrypt(self, data: str) -> str:
        return f"enc:{data}"


class TokenService:
    """Tạo ra bởi factory method có dep từ register_instance."""
    def __init__(self, key: str):
        self.key = key

    def sign(self, payload: str) -> str:
        return f"{payload}.{self.key}"


class SimpleConfig:
    """Config class: chỉ factory method không có dep."""

    def cipher(self) -> Cipher:
        return Cipher()


class FullConfig:
    """Config class: factory không dep + factory có dep."""

    def cipher(self) -> Cipher:
        return Cipher()

    def token_service(self, cfg: AppConfig) -> TokenService:
        return TokenService(cfg.secret_key)


# ===========================================================================
# Tests — register()
# ===========================================================================

class TestRegister:

    def test_get_class_without_deps(self):
        """register() class không có dep → có thể get() được."""
        c = XimeContainer().register(IdFactory).build()
        assert isinstance(c.get(IdFactory), IdFactory)

    def test_singleton_behavior(self):
        """register() tạo singleton — hai lần get() cùng instance."""
        c = XimeContainer().register(IdFactory).build()
        assert c.get(IdFactory) is c.get(IdFactory)

    def test_constructor_injection(self):
        """register() nhiều class → framework inject dep qua constructor."""
        c = XimeContainer().register(IdFactory, CredentialFactory).build()
        factory = c.get(CredentialFactory)
        assert isinstance(factory, CredentialFactory)
        assert isinstance(factory.id_factory, IdFactory)

    def test_shared_singleton_across_dependents(self):
        """Singleton được chia sẻ: cùng instance dù lấy trực tiếp hay qua dep."""
        c = XimeContainer().register(IdFactory, CredentialFactory).build()
        assert c.get(CredentialFactory).id_factory is c.get(IdFactory)

    def test_chained_deps(self):
        """Chuỗi dep 3 tầng: AuthService → CredentialFactory → IdFactory."""
        c = XimeContainer().register(IdFactory, CredentialFactory, AuthService).build()
        svc = c.get(AuthService)
        assert isinstance(svc, AuthService)
        assert isinstance(svc.factory, CredentialFactory)
        assert isinstance(svc.factory.id_factory, IdFactory)

    def test_registered_class_works_correctly(self):
        """End-to-end: factory tạo đúng output."""
        c = XimeContainer().register(IdFactory, CredentialFactory).build()
        result = c.get(CredentialFactory).create()
        assert result == {"id": "generated-id"}

    def test_class_without_type_hint_param_treated_as_no_dep(self):
        """Class có param thiếu type hint → framework bỏ qua param đó (không inject).
        Đây là thiết kế có chủ đích: thiếu hint = không phải DI dep."""

        class ServiceWithoutHint:
            def __init__(self, helper):  # không có type hint
                self.helper = helper

        # Không raise lúc build — class được đăng ký với dep rỗng
        c = XimeContainer().register(ServiceWithoutHint).build()
        # Nhưng get() sẽ fail vì helper không được inject → TypeError
        with pytest.raises(TypeError):
            c.get(ServiceWithoutHint)

    def test_register_after_build_raises(self):
        """register() sau build() → RuntimeError."""
        c = XimeContainer().build()
        with pytest.raises(RuntimeError, match="already built"):
            c.register(IdFactory)

    def test_register_unresolved_dep_raises_at_build(self):
        """Class cần dep chưa đăng ký → UnregisteredDependencyException lúc build."""
        from xime.core.exception import UnregisteredDependencyException

        # CredentialFactory cần IdFactory nhưng IdFactory chưa register
        with pytest.raises(UnregisteredDependencyException):
            XimeContainer().register(CredentialFactory).build()

    def test_register_combined_with_scan(self):
        """register() kết hợp scan(): class từ cả hai nguồn đều được inject."""
        c = (
            XimeContainer()
            .scan("sample.repository")   # UserRepository từ scan
            .register(IdFactory)          # IdFactory từ register
            .build()
        )
        from sample.repository.user_repository import UserRepository
        assert isinstance(c.get(UserRepository), UserRepository)
        assert isinstance(c.get(IdFactory), IdFactory)


# ===========================================================================
# Tests — configure()
# ===========================================================================

class TestConfigure:

    def test_factory_method_without_deps(self):
        """Factory method không có tham số → singleton được tạo."""
        c = XimeContainer().configure(SimpleConfig).build()
        assert isinstance(c.get(Cipher), Cipher)

    def test_factory_singleton(self):
        """configure() tạo singleton — hai lần get() cùng instance."""
        c = XimeContainer().configure(SimpleConfig).build()
        assert c.get(Cipher) is c.get(Cipher)

    def test_factory_method_with_dep_from_register_instance(self):
        """Factory method nhận dep từ register_instance."""
        cfg = AppConfig()
        c = (
            XimeContainer()
            .register_instance(AppConfig, cfg)
            .configure(FullConfig)
            .build()
        )
        svc = c.get(TokenService)
        assert isinstance(svc, TokenService)
        assert svc.key == "test-secret"

    def test_factory_result_uses_dep_correctly(self):
        """Factory method dùng dep để khởi tạo đúng cách."""
        cfg = AppConfig()
        c = (
            XimeContainer()
            .register_instance(AppConfig, cfg)
            .configure(FullConfig)
            .build()
        )
        assert c.get(TokenService).sign("data") == "data.test-secret"

    def test_multiple_factories_in_one_config_class(self):
        """Một config class có thể định nghĩa nhiều factory method."""
        cfg = AppConfig()
        c = (
            XimeContainer()
            .register_instance(AppConfig, cfg)
            .configure(FullConfig)
            .build()
        )
        assert isinstance(c.get(Cipher), Cipher)
        assert isinstance(c.get(TokenService), TokenService)

    def test_factory_provided_type_injectable_into_registered_class(self):
        """Type từ configure() có thể được inject vào class từ register()."""

        class Consumer:
            def __init__(self, cipher: Cipher):
                self.cipher = cipher

        c = (
            XimeContainer()
            .configure(SimpleConfig)
            .register(Consumer)
            .build()
        )
        consumer = c.get(Consumer)
        assert isinstance(consumer.cipher, Cipher)
        assert consumer.cipher is c.get(Cipher)

    def test_private_methods_ignored(self):
        """Method bắt đầu bằng _ không được coi là factory."""

        class ConfigWithPrivate:
            def _hidden(self) -> Cipher:
                return Cipher()

        c = XimeContainer().configure(ConfigWithPrivate).build()
        with pytest.raises(KeyError):
            c.get(Cipher)

    def test_method_without_return_type_ignored(self):
        """Method không có return type annotation bị bỏ qua."""

        class ConfigNoReturn:
            def make(self):  # không có return type
                return Cipher()

        c = XimeContainer().configure(ConfigNoReturn).build()
        with pytest.raises(KeyError):
            c.get(Cipher)

    def test_configure_after_build_raises(self):
        """configure() sau build() → RuntimeError."""
        c = XimeContainer().build()
        with pytest.raises(RuntimeError, match="already built"):
            c.configure(SimpleConfig)

    def test_configure_with_protocol_dep_resolved_via_bind(self):
        """Factory method có Protocol dep → được resolve qua bind()."""

        class IHasher(Protocol):
            def hash(self, data: str) -> str: ...

        class Sha256Hasher:
            def hash(self, data: str) -> str:
                return f"sha256:{data}"

        class HashConfig:
            def token_service(self, hasher: IHasher) -> TokenService:
                return TokenService(hasher.hash("secret"))

        c = (
            XimeContainer()
            .register(Sha256Hasher)
            .bind({IHasher: Sha256Hasher})
            .configure(HashConfig)
            .build()
        )
        svc = c.get(TokenService)
        assert svc.key == "sha256:secret"


# ===========================================================================
# Tests — ConfigClassLoader trực tiếp (unit tests)
# ===========================================================================

class TestConfigClassLoader:

    def test_config_class_with_constructor_params_raises(self):
        """Config class có tham số __init__ → ConfigClassError."""

        class BadConfig:
            def __init__(self, dep: IdFactory):
                self.dep = dep

            def cipher(self) -> Cipher:
                return Cipher()

        with pytest.raises(ConfigClassError):
            ConfigClassLoader().load(BadConfig)

    def test_extracts_correct_provided_types(self):
        entries = ConfigClassLoader().load(FullConfig)
        provided = {e.provided_type for e in entries}
        assert Cipher in provided
        assert TokenService in provided

    def test_no_dep_method_has_empty_dependencies(self):
        entries = ConfigClassLoader().load(SimpleConfig)
        entry = next(e for e in entries if e.provided_type is Cipher)
        assert entry.dependencies == {}

    def test_dep_method_has_correct_dependencies(self):
        entries = ConfigClassLoader().load(FullConfig)
        entry = next(e for e in entries if e.provided_type is TokenService)
        assert entry.dependencies == {"cfg": AppConfig}

    def test_factory_fn_is_callable(self):
        entries = ConfigClassLoader().load(SimpleConfig)
        for entry in entries:
            assert callable(entry.factory_fn)

    def test_factory_fn_produces_correct_instance(self):
        """Gọi trực tiếp factory_fn (không qua DI) → ra đúng kiểu."""
        entries = ConfigClassLoader().load(SimpleConfig)
        entry = next(e for e in entries if e.provided_type is Cipher)
        result = entry.factory_fn()
        assert isinstance(result, Cipher)

    def test_private_method_not_extracted(self):
        class ConfigWithPrivate:
            def _hidden(self) -> Cipher:
                return Cipher()

            def visible(self) -> IdFactory:
                return IdFactory()

        entries = ConfigClassLoader().load(ConfigWithPrivate)
        provided = {e.provided_type for e in entries}
        assert Cipher not in provided
        assert IdFactory in provided

    def test_method_without_return_type_not_extracted(self):
        class ConfigPartial:
            def no_return(self):
                return Cipher()

            def with_return(self) -> IdFactory:
                return IdFactory()

        entries = ConfigClassLoader().load(ConfigPartial)
        provided = {e.provided_type for e in entries}
        assert Cipher not in provided
        assert IdFactory in provided
