from xime.core.container.graph import DependencyGraph
from xime.core.container.resolver import ResolvedMap
from xime.core.exception import (
    BindingValidationException,
    CircularDependencyException,
    MissingBindingException,
    MissingImplementationException,
    MultipleImplementationException,
    UnregisteredDependencyException,
)
from xime.core.metadata.type_utils import get_protocol_methods, is_protocol


def _hint_for(dep_type: type) -> str | None:
    """Point at the registry that class actually comes from.

    Two registries feed the container OUTSIDE dependency.scan(): RefData tables
    (configure_refdata) and ProcessLink handlers (configure_link). Neither can
    ever be reached by scanning a package, so the default hint is not merely
    unhelpful for them - it is a road with no end. That matters most in a
    hand-built container inside a test, which is exactly where a reader has no
    orchestrator to compare against.
    Hai registry nap vao container NGOAI dependency.scan(): bang RefData va
    handler ProcessLink. Khong cai nao toi duoc bang cach quet mot package, nen
    goi y mac dinh khong chi vo ich voi chung - no la mot con duong khong co
    dich. Dieu do dat nhat trong container dung tay o test, dung cho nguoi doc
    khong co orchestrator de doi chieu.

    Returns None when the default hint is the right one - saying nothing beats
    guessing.
    """
    # Lazy import: this runs only on the failure path, and core.container must
    # not depend on core.refdata / core.link at module level.
    try:
        from xime.core.refdata import RefData
    except Exception:  # pragma: no cover - refdata is core, but stay defensive
        pass
    else:
        if isinstance(dep_type, type) and issubclass(dep_type, RefData):
            return (
                "a RefData table reaches the container through "
                "configure_refdata(), not dependency.scan()"
            )

    try:
        from xime.core.link import link_registry
    except Exception:  # pragma: no cover
        return None
    if dep_type in set(link_registry.handlers()):
        return (
            "a ProcessLink handler reaches the container through "
            "configure_link(), not dependency.scan()"
        )
    return None

class GraphValidator:
    """
    Validates the dependency graph and bindings before registration.

    Checks run in this order (fail fast on first error found):
      1. Circular dependencies
      2. Unresolved Protocol dependencies (missing, ambiguous, or missing binding)
      3. Binding correctness (impl must satisfy Protocol)
      4. Unregistered concrete dependencies (concrete dep not in scanned packages)
    """

    def validate(
        self,
        resolved: ResolvedMap,
        graph: DependencyGraph,
        bindings: dict[type, type],
        all_classes: list[type],
        instances: dict[type, object] | None = None,
        factory_provided: list[type] | None = None,
    ) -> None:
        self._check_cycles(graph)
        self._check_unresolved_protocols(resolved, all_classes, instances, factory_provided)
        self._check_bindings(bindings)
        self._check_missing_concrete_deps(resolved, all_classes, instances, factory_provided)

    # ------------------------------------------------------------------
    # 1. Circular dependency check
    # ------------------------------------------------------------------

    def _check_cycles(self, graph: DependencyGraph) -> None:
        cycles = graph.detect_cycles()
        if cycles:
            # Report only the first cycle; one error at a time.
            cycle = cycles[0]
            raise CircularDependencyException([cls.__name__ for cls in cycle])

    # ------------------------------------------------------------------
    # 2. Unresolved Protocol check
    # ------------------------------------------------------------------

    def _check_unresolved_protocols(
        self,
        resolved: ResolvedMap,
        all_classes: list[type],
        instances: dict[type, object] | None = None,
        factory_provided: list[type] | None = None,
    ) -> None:
        """
        After resolution, any dependency that is still a Protocol means
        no explicit binding was declared for it. Find out why and fail fast.

        Protocols satisfied by a pre-built instance (register_instance) or a
        factory-provided type (configure) are treated as satisfied and skipped.
        """
        # Deduplicate: one error per unresolved Protocol is enough.
        already_reported: set[type] = set()
        pre_built: set[type] = set(instances or {}) | set(factory_provided or {})

        for _cls, deps in resolved.items():
            for _param, dep_type in deps.items():
                if not is_protocol(dep_type):
                    continue
                if dep_type in already_reported:
                    continue
                if dep_type in pre_built:
                    continue  # pre-built instance satisfies this Protocol

                already_reported.add(dep_type)
                candidates = self._find_candidates(dep_type, all_classes)

                if len(candidates) == 0:
                    raise MissingImplementationException(dep_type.__name__)
                elif len(candidates) == 1:
                    # Implementation exists structurally but binding was not declared.
                    raise MissingBindingException(dep_type.__name__, candidates[0].__name__)
                else:
                    raise MultipleImplementationException(
                        dep_type.__name__,
                        [c.__name__ for c in candidates],
                    )

    def _find_candidates(self, protocol_cls: type, all_classes: list[type]) -> list[type]:
        """
        Return every non-Protocol class in all_classes that structurally
        satisfies protocol_cls (i.e. has all its declared methods).
        """
        required = get_protocol_methods(protocol_cls)
        return [
            cls
            for cls in all_classes
            if not is_protocol(cls) and self._satisfies(cls, required)
        ]

    @staticmethod
    def _satisfies(cls: type, required_methods: set[str]) -> bool:
        return all(
            callable(getattr(cls, method, None))
            for method in required_methods
        )

    # ------------------------------------------------------------------
    # 3. Missing concrete dependency check
    # ------------------------------------------------------------------

    def _check_missing_concrete_deps(
        self,
        resolved: ResolvedMap,
        all_classes: list[type],
        instances: dict[type, object] | None = None,
        factory_provided: list[type] | None = None,
    ) -> None:
        """
        Check that every concrete (non-Protocol) dependency is present in
        all_classes, pre-built instances, or factory-provided types.

        Catches the case where a class depends on a concrete type that was
        never scanned - the registry would silently skip it, causing a
        TypeError at runtime when the instance is created.
        """
        registered = set(all_classes) | set(instances or {}) | set(factory_provided or {})
        for cls, deps in resolved.items():
            for dep_type in deps.values():
                if not is_protocol(dep_type) and dep_type not in registered:
                    raise UnregisteredDependencyException(
                        cls.__name__, dep_type.__name__, hint=_hint_for(dep_type)
                    )

    # ------------------------------------------------------------------
    # 4. Binding correctness check
    # ------------------------------------------------------------------

    def _check_bindings(
        self, bindings: dict[type, type | tuple[type, ...]]
    ) -> None:
        """
        For every declared binding, verify the implementation has all methods
        required by the Protocol.

        A binding value may be a single implementation class or a tuple of
        classes (dynamic binding). For a tuple, every implementation must satisfy
        the Protocol - one bad impl fails startup.
        Value có thể là một class hoặc tuple class (dynamic binding). Với tuple,
        MỌI impl phải thỏa Protocol - sai một cái là startup fail.
        """
        for interface, target in bindings.items():
            if not is_protocol(interface):
                continue

            required = get_protocol_methods(interface)
            implementations = target if isinstance(target, tuple) else (target,)
            for implementation in implementations:
                missing = {
                    m for m in required
                    if not callable(getattr(implementation, m, None))
                }
                if missing:
                    raise BindingValidationException(
                        interface.__name__,
                        implementation.__name__,
                        sorted(missing),
                    )
