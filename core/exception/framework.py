class XimeException(Exception):
    """Base exception for all Xime framework errors."""

    pass


class StartupException(XimeException):
    """Raised when the application fails to start."""

    pass


class MissingTypeHintException(StartupException):
    """
    Raised when a constructor parameter has no type hint.
    Xime cannot resolve dependencies without type hints.
    """

    def __init__(self, class_name: str, parameter: str):
        self.class_name = class_name
        self.parameter = parameter
        super().__init__(
            f"\nMissing Type Hint\n"
            f"  Class    : {class_name}\n"
            f"  Parameter: {parameter}"
        )


class MissingImplementationException(StartupException):
    """
    Raised when an interface (Protocol) has no registered implementation.
    """

    def __init__(self, interface_name: str):
        self.interface_name = interface_name
        super().__init__(
            f"\nNo Implementation Found\n"
            f"  Interface: {interface_name}"
        )


class MultipleImplementationException(StartupException):
    """
    Raised when an interface has multiple candidates but no explicit binding.
    """

    def __init__(self, interface_name: str, candidates: list[str]):
        self.interface_name = interface_name
        self.candidates = candidates
        candidates_str = ", ".join(candidates)
        super().__init__(
            f"\nMultiple Implementations Found\n"
            f"  Interface : {interface_name}\n"
            f"  Candidates: {candidates_str}"
        )


class CircularDependencyException(StartupException):
    """
    Raised when a circular dependency is detected in the dependency graph.
    """

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        cycle_str = " → ".join(cycle)
        super().__init__(
            f"\nCircular dependency detected:\n"
            f"  {cycle_str}"
        )


class BindingValidationException(StartupException):
    """
    Raised when a bound implementation does not satisfy its Protocol interface.
    """

    def __init__(self, interface_name: str, implementation_name: str, missing_methods: list[str]):
        self.interface_name = interface_name
        self.implementation_name = implementation_name
        self.missing_methods = missing_methods
        missing_str = "\n  - ".join(missing_methods)
        super().__init__(
            f"\nBinding Validation Failed\n"
            f"  Protocol      : {interface_name}\n"
            f"  Implementation: {implementation_name}\n"
            f"  Missing methods:\n"
            f"  - {missing_str}"
        )
