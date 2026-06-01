from core.metadata.type_utils import is_protocol, resolve_constructor_hints

# Type aliases for readability
ClassDeps = dict[str, type]          # {param_name: concrete_type}
ResolvedMap = dict[type, ClassDeps]  # {class: {param_name: concrete_type}}


class TypeHintResolver:
    """
    Maps each scanned class to its concrete dependencies.

    For each constructor parameter:
      - Regular class  → kept as-is
      - Protocol + has binding → replaced with the bound implementation
      - Protocol + no binding  → kept as-is (validator will catch it)
    """

    def resolve(
        self,
        classes: list[type],
        bindings: dict[type, type],
    ) -> ResolvedMap:
        """
        Args:
            classes:  list of eligible classes from PackageScanner
            bindings: explicit Protocol → Implementation map from user config

        Returns:
            {cls: {param_name: resolved_type}}
            resolved_type is always a concrete class when a binding exists,
            or left as the original type when no binding is found.
        """
        return {
            cls: self._resolve_hints(cls, bindings)
            for cls in classes
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_hints(self, cls: type, bindings: dict[type, type]) -> ClassDeps:
        hints = resolve_constructor_hints(cls)
        return {
            param: self._resolve_one(hint_type, bindings)
            for param, hint_type in hints.items()
        }

    def _resolve_one(self, type_: type, bindings: dict[type, type]) -> type:
        """
        Resolve a single type annotation.
        Protocol with a binding → return the bound implementation.
        Anything else → return unchanged.
        """
        if is_protocol(type_) and type_ in bindings:
            return bindings[type_]
        return type_
