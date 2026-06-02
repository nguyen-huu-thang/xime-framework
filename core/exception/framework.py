class XimeException(Exception):
    """Base exception for all Xime framework errors."""

    pass


class StartupException(XimeException):
    """Raised when the application fails to start."""

    pass


class MissingTypeHintException(StartupException):
    """
    Raised when a string annotation (forward reference) in a constructor
    cannot be resolved at startup. Xime cannot build the dependency graph
    without being able to evaluate all type hints.
    """

    def __init__(self, class_name: str, detail: str):
        self.class_name = class_name
        self.detail = detail
        super().__init__(
            f"\nUnresolvable Type Annotation\n"
            f"  Class : {class_name}\n"
            f"  Detail: {detail}"
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


class UnregisteredDependencyException(StartupException):
    """
    Raised when a class depends on a concrete type that was never scanned.
    Unlike MissingImplementationException (for Protocols), this targets
    plain classes that are simply absent from all scanned packages.
    """

    def __init__(self, dependent_name: str, dependency_name: str):
        self.dependent_name = dependent_name
        self.dependency_name = dependency_name
        super().__init__(
            f"\nUnregistered Dependency\n"
            f"  Class     : {dependent_name}\n"
            f"  Dependency: {dependency_name}\n"
            f"  Hint      : add the package containing '{dependency_name}' to dependency.scan()"
        )


class MissingBindingException(StartupException):
    """
    Raised when a Protocol has exactly one structural candidate but no
    explicit binding was declared. The implementation exists — the developer
    only needs to add dependency.bind({Interface: Implementation}).
    """

    def __init__(self, interface_name: str, candidate_name: str):
        self.interface_name = interface_name
        self.candidate_name = candidate_name
        super().__init__(
            f"\nMissing Explicit Binding\n"
            f"  Interface : {interface_name}\n"
            f"  Candidate : {candidate_name}\n"
            f"  Hint      : add dependency.bind({{{interface_name}: {candidate_name}}}) in config/dependency.py"
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


# ---------------------------------------------------------------------------
# Runtime — Security
# ---------------------------------------------------------------------------

class SecurityException(XimeException):
    """Base for security-related runtime exceptions."""

    pass


class AuthenticationException(SecurityException):
    """
    Raised when credentials cannot be verified.
    Implementations of AuthenticationManager should raise this on failure.
    """

    def __init__(self, message: str = "Authentication failed"):
        self.message = message
        super().__init__(f"\nAuthentication Failed\n  {message}")


class AuthorizationException(SecurityException):
    """
    Raised when the current identity lacks a required permission.
    Implementations of AuthorizationManager should raise this on failure.
    """

    def __init__(self, message: str = "Access denied"):
        self.message = message
        super().__init__(f"\nAccess Denied\n  {message}")
