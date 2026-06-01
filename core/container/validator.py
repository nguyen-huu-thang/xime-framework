from core.container.graph import DependencyGraph
from core.container.resolver import ResolvedMap
from core.exception import (
    BindingValidationException,
    CircularDependencyException,
    MissingImplementationException,
    MultipleImplementationException,
)
from core.metadata.type_utils import get_protocol_methods, is_protocol


class GraphValidator:
    """
    Validates the dependency graph and bindings before registration.

    Checks run in this order (fail fast on first error found):
      1. Circular dependencies
      2. Unresolved Protocol dependencies (missing or ambiguous)
      3. Binding correctness (impl must satisfy Protocol)
    """

    def validate(
        self,
        resolved: ResolvedMap,
        graph: DependencyGraph,
        bindings: dict[type, type],
        all_classes: list[type],
    ) -> None:
        self._check_cycles(graph)
        self._check_unresolved_protocols(resolved, all_classes)
        self._check_bindings(bindings)

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
    ) -> None:
        """
        After resolution, any dependency that is still a Protocol means
        no explicit binding was declared for it. Find out why and fail fast.
        """
        # Deduplicate: one error per unresolved Protocol is enough.
        already_reported: set[type] = set()

        for _cls, deps in resolved.items():
            for _param, dep_type in deps.items():
                if not is_protocol(dep_type):
                    continue
                if dep_type in already_reported:
                    continue

                already_reported.add(dep_type)
                candidates = self._find_candidates(dep_type, all_classes)

                if len(candidates) <= 1:
                    # 0 candidates → truly missing.
                    # 1 candidate → user forgot to add an explicit binding.
                    raise MissingImplementationException(dep_type.__name__)
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
    # 3. Binding correctness check
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
