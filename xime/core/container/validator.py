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
    ) -> None:
        self._check_cycles(graph)
        self._check_unresolved_protocols(resolved, all_classes, instances)
        self._check_bindings(bindings)
        self._check_missing_concrete_deps(resolved, all_classes, instances)

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
    ) -> None:
        """
        After resolution, any dependency that is still a Protocol means
        no explicit binding was declared for it. Find out why and fail fast.

        Protocols that have a pre-built instance registered (via register_instance)
        are treated as satisfied and skipped — the registry will wire them directly.
        """
        # Deduplicate: one error per unresolved Protocol is enough.
        already_reported: set[type] = set()
        pre_built: set[type] = set(instances or {})

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
    ) -> None:
        """
        Check that every concrete (non-Protocol) dependency is present in
        all_classes or pre-built instances.

        Catches the case where a class depends on a concrete type that was
        never scanned — the registry would silently skip it, causing a
        TypeError at runtime when the instance is created.
        """
        registered = set(all_classes) | set(instances or {})
        for cls, deps in resolved.items():
            for dep_type in deps.values():
                if not is_protocol(dep_type) and dep_type not in registered:
                    raise UnregisteredDependencyException(cls.__name__, dep_type.__name__)

    # ------------------------------------------------------------------
    # 4. Binding correctness check
    # ------------------------------------------------------------------

    def _check_bindings(self, bindings: dict[type, type]) -> None:
        """
        For every declared binding, verify the implementation has all
        methods required by the Protocol.
        """
        for interface, implementation in bindings.items():
            if not is_protocol(interface):
                continue

            required = get_protocol_methods(interface)
            missing = {m for m in required if not callable(getattr(implementation, m, None))}

            if missing:
                raise BindingValidationException(
                    interface.__name__,
                    implementation.__name__,
                    sorted(missing),
                )
