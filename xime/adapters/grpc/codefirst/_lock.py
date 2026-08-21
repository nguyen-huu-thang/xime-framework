from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

# Lock-file schema version - bump if the on-disk format changes.
_LOCK_VERSION = 1


@dataclass
class MessageLock:
    """Persisted field-number assignment for one message."""

    fields: dict[str, int] = field(default_factory=dict)
    reserved_numbers: list[int] = field(default_factory=list)
    reserved_names: list[str] = field(default_factory=list)


class LockFile:
    """Persists proto field numbers so they stay stable across regeneration.

    Protobuf identifies fields by NUMBER, not name. If a regen reshuffled the
    numbers, old clients and new servers would silently disagree on the wire.
    The lock file remembers each field's number and is committed to git.
    Protobuf định danh field bằng SỐ, không phải tên. Lock file nhớ số từng field
    và được commit vào git để tránh phá tương thích nhị phân.

    Deleted fields are recorded as `reserved` and their numbers are NEVER reused
    (protobuf best practice).
    Field bị xoá được ghi `reserved`, số của nó KHÔNG bao giờ tái sử dụng.
    """

    def __init__(self, messages: dict[str, MessageLock] | None = None) -> None:
        self.messages: dict[str, MessageLock] = messages or {}

    # ------------------------------------------------------------------
    # Field-number assignment
    # ------------------------------------------------------------------

    def assign_numbers(self, message_name: str, py_fields: list[str]) -> dict[str, int]:
        """Return {field_name: number} for the current fields, mutating the lock.

        - Existing fields keep their numbers.
        - New fields get the next free number (skipping reserved ones).
        - Removed fields move to reserved (number never reused).
        """
        record = self.messages.setdefault(message_name, MessageLock())
        result: dict[str, int] = {}

        # 1) Keep numbers for fields already known.
        for name in py_fields:
            if name in record.fields:
                result[name] = record.fields[name]

        # 2) Assign new fields the next free number.
        used = set(record.fields.values()) | set(record.reserved_numbers)
        next_num = (max(used) + 1) if used else 1
        for name in py_fields:
            if name not in result:
                result[name] = next_num
                next_num += 1

        # 3) Reserve numbers/names of removed fields.
        current = set(py_fields)
        for old_name, old_num in record.fields.items():
            if old_name not in current:
                if old_num not in record.reserved_numbers:
                    record.reserved_numbers.append(old_num)
                if old_name not in record.reserved_names:
                    record.reserved_names.append(old_name)

        record.fields = result
        record.reserved_numbers.sort()
        return result

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str) -> LockFile:
        """Load a lock file, or return an empty one if it does not exist."""
        if not os.path.exists(path):
            return cls()
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        messages = {
            name: MessageLock(
                fields=dict(rec.get("fields", {})),
                reserved_numbers=list(rec.get("reserved_numbers", [])),
                reserved_names=list(rec.get("reserved_names", [])),
            )
            for name, rec in data.get("messages", {}).items()
        }
        return cls(messages)

    def to_dict(self) -> dict:
        """Serialize to a JSON-ready dict (deterministic key order)."""
        return {
            "version": _LOCK_VERSION,
            "messages": {
                name: {
                    "fields": rec.fields,
                    "reserved_numbers": rec.reserved_numbers,
                    "reserved_names": rec.reserved_names,
                }
                for name, rec in sorted(self.messages.items())
            },
        }

    def save(self, path: str) -> None:
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
