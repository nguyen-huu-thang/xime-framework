from __future__ import annotations


class BindingConfig:
    """
    Collects DI configuration declared in the application's config/dependency.py.

    Bootstrap reads this object after the user's config module runs and
    forwards its state to XimeContainer.

    Typical usage in app/config/dependency.py:
        from xime.core.config import BindingConfig

        dependency = BindingConfig()
        dependency.scan("app.service", "app.repository")
        dependency.bind({UserRepository: JpaUserRepository})
        dependency.register(IdFactory, IdService)
        dependency.configure(DomainConfig)
    """

    def __init__(self) -> None:
        self._packages: list[str] = []
        self._bindings: dict[type, type] = {}
        self._explicit_classes: list[type] = []
        self._config_classes: list[type] = []
        self._order_rules: list[list[type]] = []

    def scan(self, *package_names: str) -> None:
        """Register one or more package paths to scan for DI candidates."""
        self._packages.extend(package_names)

    def bind(self, bindings: dict[type, type]) -> None:
        """
        Declare explicit Protocol → Implementation mappings.
        Later calls overwrite earlier bindings for the same key.
        """
        self._bindings.update(bindings)

    def register(self, *classes: type) -> None:
        """
        Explicitly register individual classes into the DI container without
        scanning their package.

        Use this for classes in excluded packages (e.g. domain factories,
        domain services) that still need to be singletons.  The framework
        applies normal constructor injection — every __init__ parameter must
        have a type hint.
        """
        self._explicit_classes.extend(classes)

    def order(self, *rules: list[type]) -> None:
        """
        Declare post_construct() execution order for classes that have no
        direct constructor dependency relationship.

        Equivalent to @DependsOn in Spring Boot, but declared centrally in
        the config file instead of as an annotation on individual classes.

        Each list is an ordered chain — [A, B, C] means:
            A.post_construct() completes before B starts,
            B.post_construct() completes before C starts.

        Multiple chains can be passed in one call or across multiple calls:

            dependency.order(
                [TrustSelfCertificateLoader, GrpcExternalCredentialsProvider],
                [DatabasePool, UserRepository, UserService],
            )

        Framework validates at startup (fail fast):
        - Every class must be registered in the DI container.
        - No cycles, including combined with constructor dependency order.

        Typical use case: A.post_construct() writes to a shared resource that
        B.post_construct() reads, but A and B have no constructor dependency
        on each other.
        """
        self._order_rules.extend(rules)

    def configure(self, config_class: type) -> None:
        """
        Register a config class whose methods act as manual bean factories.

        Each public method with a return type annotation is treated as a
        factory that produces one singleton.  Method parameters are injected
        by the container at startup.  The config class itself must be
        stateless (no __init__ parameters).

        Example:
            class DomainConfig:
                def credential_factory(self) -> CredentialAuthenticationFactory:
                    return CredentialAuthenticationFactory()

                def key_service(self, cfg: AppConfig) -> KeyEncryptionService:
                    return AesKeyEncryptionService(cfg.secret_key)

            dependency.configure(DomainConfig)
        """
        self._config_classes.append(config_class)

    # ------------------------------------------------------------------
    # Read-only properties for XimeContainer / Bootstrap
    # ------------------------------------------------------------------

    @property
    def packages(self) -> tuple[str, ...]:
        """Immutable snapshot of registered scan packages."""
        return tuple(self._packages)

    @property
    def bindings(self) -> dict[type, type]:
        """Shallow copy of the current Protocol → Implementation map."""
        return dict(self._bindings)

    @property
    def explicit_classes(self) -> tuple[type, ...]:
        """Immutable snapshot of explicitly registered classes."""
        return tuple(self._explicit_classes)

    @property
    def config_classes(self) -> tuple[type, ...]:
        """Immutable snapshot of registered config classes."""
        return tuple(self._config_classes)

    @property
    def order_rules(self) -> tuple[list[type], ...]:
        """Immutable snapshot of post_construct() ordering rules."""
        return tuple(self._order_rules)
