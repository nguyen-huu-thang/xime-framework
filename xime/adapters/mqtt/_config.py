from __future__ import annotations

from pydantic import BaseModel

from xime.core.config.runtime import RuntimeConfig

from ._runtime import MqttConnection
from ._topic import is_valid_filter


class MqttTlsConfig(BaseModel):
    """Optional TLS settings for the broker connection."""

    ca_certs: str | None = None
    certfile: str | None = None
    keyfile: str | None = None


class MqttLwtConfig(BaseModel):
    """Last Will and Testament published by the broker if the client drops."""

    topic: str
    payload: str = ""
    qos: int = 0
    retain: bool = False


class MqttRpcConfig(BaseModel):
    """Reply-topic policy for `@rpc` handlers (F17).

    MQTT v5 request/reply lets the CALLER name the topic the reply goes to, and
    the adapter publishes it using the SERVICE's broker credentials. Where the
    broker enforces per-client ACLs, that lets a caller reach a topic its own
    ACL forbids by borrowing ours - a confused deputy.
    MQTT v5 cho BÊN GỌI tự đặt topic nhận reply, mà adapter publish bằng
    credential của DỊCH VỤ. Broker có phân quyền theo client thì bên gọi mượn
    được quyền của ta để ghi vào topic mà ACL của nó cấm.

    `reply_topics` lists the topic filters a reply is expected to land on. It is
    ADVISORY by default: a reply outside the list is still published, but a
    WARNING names it. Declaring nothing keeps the old behaviour and produces one
    startup warning instead of one per message.
    `reply_topics` là danh sách filter mà reply được phép rơi vào. Mặc định chỉ
    CẢNH BÁO: reply ngoài danh sách vẫn được gửi, kèm một dòng WARNING. Không
    khai gì thì giữ nguyên hành vi cũ và chỉ cảnh báo MỘT lần lúc khởi động.

        mqtt:
          rpc:
            reply_topics:
              - nhamay/reply/#
              - devices/+/reply
    """

    reply_topics: list[str] = []

    @classmethod
    def resolve(cls, raw: object) -> MqttRpcConfig:
        """Build from the raw `mqtt.rpc` block; fail-fast on an unusable filter.

        A malformed filter can never match, so it would silently turn every
        reply into a warning - the shape of a check that cries wolf, which is
        the shape of a check people switch off.
        Filter sai cú pháp thì không bao giờ khớp, nên nó biến MỌI reply thành
        cảnh báo - đúng hình dạng của một phép dò kêu oan, tức phép dò sẽ bị tắt.
        """
        block = raw if isinstance(raw, dict) else {}
        topics = block.get("reply_topics") or []
        if isinstance(topics, str):
            topics = [topics]
        if not isinstance(topics, list):
            raise ValueError(
                "mqtt.rpc.reply_topics must be a list of MQTT topic filters, "
                f"got {type(topics).__name__}."
            )
        bad = [t for t in topics if not isinstance(t, str) or not is_valid_filter(t)]
        if bad:
            raise ValueError(
                f"mqtt.rpc.reply_topics contains invalid topic filter(s): {bad!r}. "
                "'#' must stand alone as the final level; '+' must occupy a whole level."
            )
        return cls(reply_topics=list(topics))


class MqttConfig(BaseModel):
    """Runtime configuration for one MQTT client, read from the 'mqtt' block.

        mqtt:
          host: broker.local        # required - missing -> fail-fast
          port: 1883
          username: svc             # optional
          password: secret          # optional
          client_id: data-service   # optional - defaults to the adapter's id
          keepalive: 60
          default_qos: 0
          # Số handler chạy song song tối đa. >1: message được xử lý ĐỒNG THỜI nên
          # KHÔNG đảm bảo thứ tự (kể cả cùng topic). Đặt =1 để xử lý TUẦN TỰ, giữ
          # đúng thứ tự broker giao (đánh đổi throughput).
          # >1 = concurrent, no ordering guarantee; =1 = sequential, ordered.
          max_concurrency: 16       # in-flight message handlers
          reconnect_delay: 3.0      # seconds between reconnect attempts
          tls:
            ca_certs: /etc/ssl/ca.pem
            certfile: /etc/ssl/client.pem
            keyfile: /etc/ssl/client.key
          lwt:
            topic: status/data-service
            payload: offline
            qos: 1
            retain: true
          rpc:
            # Topic filter mà reply RPC được phép rơi vào (F17). Mặc định rỗng =
            # giữ hành vi cũ, chỉ cảnh báo một lần lúc khởi động.
            reply_topics:
              - nhamay/reply/#
    """

    host: str
    port: int = 1883
    username: str | None = None
    password: str | None = None
    client_id: str | None = None
    keepalive: int = 60
    default_qos: int = 0
    max_concurrency: int = 16
    reconnect_delay: float = 3.0
    tls: MqttTlsConfig | None = None
    lwt: MqttLwtConfig | None = None
    rpc: MqttRpcConfig = MqttRpcConfig()

    @classmethod
    def resolve(cls, runtime: RuntimeConfig, client_id: str) -> MqttConfig:
        """Build the config from the 'mqtt' block; fail-fast if host is missing."""
        raw = runtime.get("mqtt")
        raw = raw if isinstance(raw, dict) else {}

        host = raw.get("host")
        if not host:
            raise ValueError(
                "mqtt.host is not configured. "
                "Add 'mqtt.host' to resources/application.yml."
            )

        tls = MqttTlsConfig(**raw["tls"]) if isinstance(raw.get("tls"), dict) else None
        lwt = MqttLwtConfig(**raw["lwt"]) if isinstance(raw.get("lwt"), dict) else None

        return cls(
            host=host,
            port=int(raw.get("port", 1883)),
            username=raw.get("username"),
            password=raw.get("password"),
            client_id=raw.get("client_id") or client_id,
            keepalive=int(raw.get("keepalive", 60)),
            default_qos=int(raw.get("default_qos", 0)),
            max_concurrency=int(raw.get("max_concurrency", 16)),
            reconnect_delay=float(raw.get("reconnect_delay", 3.0)),
            tls=tls,
            lwt=lwt,
            rpc=MqttRpcConfig.resolve(raw.get("rpc")),
        )


# ---------------------------------------------------------------------------
# Registry — controller packages, error mappings, shared connections
# ---------------------------------------------------------------------------

class _MqttRegistry:
    """Module-level singleton read by MqttAdapter and MqttPublisher.

    Holds controller packages, exception -> error-code mappings, and one shared
    MqttConnection per client_id so the adapter and the publisher resolve the
    same live client. Follows the explicit-call pattern of socket_registry.
    Giữ gói controller, map lỗi, và MqttConnection dùng chung theo client_id.
    """

    def __init__(self) -> None:
        self._packages: list[str] = []
        self._error_mappings: dict[type[Exception], str] = {}
        self._connections: dict[str, MqttConnection] = {}

    def add_packages(self, *packages: str) -> None:
        self._packages.extend(packages)

    def get_packages(self) -> list[str]:
        return list(self._packages)

    def add_error_mappings(self, mappings: dict[type[Exception], str]) -> None:
        self._error_mappings.update(mappings)

    def get_error_mappings(self) -> dict[type[Exception], str]:
        return dict(self._error_mappings)

    def connection(self, client_id: str) -> MqttConnection:
        """Get or create the shared connection holder for a client_id."""
        conn = self._connections.get(client_id)
        if conn is None:
            conn = MqttConnection(client_id)
            self._connections[client_id] = conn
        return conn

    def reset(self) -> None:
        """Clear all registrations - test cleanup only."""
        self._packages.clear()
        self._error_mappings.clear()
        self._connections.clear()


mqtt_registry = _MqttRegistry()


def configure_mqtt_controllers(*packages: str) -> None:
    """Register packages that contain MQTT controller classes.

    Call once in your config layer (e.g. config/mqtt.py). MqttAdapter reads this
    registry after DI startup and builds the topic dispatch table.
    These packages must ALSO be in dependency.scan() so DI creates the instances.

    Example:
        from xime.adapters.mqtt import configure_mqtt_controllers
        configure_mqtt_controllers("api.mqtt")
    """
    mqtt_registry.add_packages(*packages)


def configure_mqtt_error_mappings(mappings: dict[type[Exception], str]) -> None:
    """Map business exceptions to error codes returned on RPC failures.

    Unmapped exceptions default to "INTERNAL" with a generic message so internal
    details never leak, mirroring the socket/gRPC error policy.
    Lỗi không map -> "INTERNAL" message chung, không lộ chi tiết nội bộ.
    """
    mqtt_registry.add_error_mappings(mappings)
