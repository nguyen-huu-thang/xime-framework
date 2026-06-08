from __future__ import annotations

"""Naming and shape conventions for streaming RPCs.

gRPC client-streaming requires every message in the stream to share one type,
but an upload needs to send request metadata first, then raw chunks. We resolve
this with a generated chunk-wrapper message using a `oneof`.
gRPC client-stream yêu cầu mọi message cùng một type, nhưng upload cần gửi metadata
trước rồi tới chunk. Giải bằng message chunk-wrapper dùng `oneof`.

Upload (CLIENT_STREAM), e.g. request EncryptRequest:

    message EncryptChunk {
        oneof payload {
            EncryptRequest metadata = 1;   // first message
            bytes          chunk    = 2;   // subsequent messages
        }
    }
    rpc Encrypt(stream EncryptChunk) returns (EncryptResponse);

Download (SERVER_STREAM):

    message DownloadChunk { bytes chunk = 1; }
    rpc Download(DownloadRequest) returns (stream DownloadChunk);
"""

# Field numbers inside the generated wrapper messages — fixed by convention,
# so they need no lock entry.
# Số field trong wrapper — cố định theo quy ước, không cần lock.
UPLOAD_METADATA_FIELD = 1
UPLOAD_CHUNK_FIELD = 2
DOWNLOAD_CHUNK_FIELD = 1


def upload_wrapper_name(rpc_name: str) -> str:
    """EncryptChunk for rpc Encrypt."""
    return f"{rpc_name}Chunk"


def download_wrapper_name(rpc_name: str) -> str:
    """DownloadChunk for rpc Download."""
    return f"{rpc_name}Chunk"
