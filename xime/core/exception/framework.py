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
    explicit binding was declared. The implementation exists - the developer
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


class InvalidOrderRuleException(StartupException):
    """
    Raised when a class passed to dependency.order() is not registered
    in the DI container.
    """

    def __init__(self, unknown_classes: str):
        self.unknown_classes = unknown_classes
        super().__init__(
            f"\nInitialization Order Error\n"
            f"  Classes not found in DI container: {unknown_classes}\n"
            f"  Every class in dependency.order() must be registered.\n"
            f"  Check dependency.order() in config/dependency.py"
        )


class OrderRuleCycleException(StartupException):
    """
    Raised when dependency.order() rules create a cycle, either within
    the declared rules or in combination with constructor dependency order.
    """

    def __init__(self, cycle: list[str]):
        self.cycle = cycle
        cycle_str = " → ".join(cycle)
        super().__init__(
            f"\nInitialization Order Conflict\n"
            f"  A cycle was detected in the combined dependency and order rules:\n"
            f"  {cycle_str}\n"
            f"  Check dependency.order() in config/dependency.py"
        )


# ---------------------------------------------------------------------------
# Runtime - Security
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


# ---------------------------------------------------------------------------
# Runtime - Socket adapter
# ---------------------------------------------------------------------------

class SocketException(XimeException):
    """Base for Socket-adapter runtime exceptions."""

    pass


class ProtocolError(SocketException):
    """
    Raised when a frame on the wire is malformed - bad magic bytes or an
    unsupported protocol version. Indicates the peer is not speaking the
    Xime socket protocol (or a version mismatch).
    Frame sai định dạng (magic/version) - peer không nói đúng protocol Xime.
    """

    pass


class EndpointNotFound(SocketException):
    """Raised when a client invokes an endpoint name that is not registered."""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        super().__init__(f"Socket endpoint '{endpoint}' not found")


class SessionTimeout(SocketException):
    """Raised inside a stream handler when its session exceeds the idle timeout.

    Surfaced through UploadStream so the handler unwinds cleanly instead of
    hanging forever when the peer disappears without sending STREAM_END.
    Đẩy vào UploadStream để handler thoát sạch khi peer biến mất giữa chừng.
    """

    def __init__(self, session_id: int):
        self.session_id = session_id
        super().__init__(f"Socket session {session_id} timed out")


class SocketCommandError(SocketException):
    """Raised on the client side when the server returns an ERROR frame.

    Carries the server-supplied error code (from configure_socket_error_mappings)
    and message so the caller can branch on it.
    Mang theo code lỗi server gửi về để client phân nhánh xử lý.
    """

    def __init__(self, code: str, message: str):
        self.code = code
        self.error_message = message
        super().__init__(f"[{code}] {message}")


class GrpcClientException(XimeException):
    """Base for errors raised by generated gRPC client SDKs (XimeGrpcChannel)."""


class RemoteCallError(GrpcClientException):
    """Raised when a remote gRPC call returns a non-OK status.

    Mirrors SocketCommandError for the gRPC transport. Carries:
    - status : gRPC StatusCode name (e.g. "NOT_FOUND", "INTERNAL")
    - code   : server-side exception class name from the `xime-error` trailing
               metadata set by ErrorMappingInterceptor ("" for non-Xime servers)
    - path   : full method path (e.g. "/xime.internal.KeyController/GetKeys")
    Gương của SocketCommandError cho transport gRPC: status là tên StatusCode,
    code là tên exception phía server (trailing metadata `xime-error`,
    rỗng nếu server không phải Xime), path là method bị lỗi.
    """

    def __init__(self, status: str, code: str, message: str, path: str):
        self.status = status
        self.code = code
        self.error_message = message
        self.path = path
        prefix = f"{status}/{code}" if code else status
        super().__init__(f"[{prefix}] {path}: {message}")


class RemoteCallTimeout(RemoteCallError):
    """The call exceeded its deadline (StatusCode.DEADLINE_EXCEEDED)."""


class RemoteServiceUnavailable(RemoteCallError):
    """The target service cannot be reached (StatusCode.UNAVAILABLE)."""
