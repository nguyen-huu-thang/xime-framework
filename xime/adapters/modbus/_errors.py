"""Exception hierarchy for the Modbus adapter.

Three failure modes worth telling apart, because the right reaction differs:

  ModbusConnectionError - the device is unreachable (cable, switch, firewall,
      device rebooting). Retrying later usually helps.
  ModbusDeviceError - the device answered, and the answer was a refusal
      (illegal address, illegal function, gateway timeout). Retrying the SAME
      request will fail again; the request or the model is wrong.
  ModbusCodecError - the bytes arrived fine but the model cannot make sense of
      them (or of the value being written). Always a code/model problem.

Ba nhóm lỗi tách riêng vì cách xử lý khác nhau: mất kết nối thì thử lại được;
thiết bị từ chối thì thử lại vô ích; lỗi codec luôn là lỗi mô hình/code.
"""

from __future__ import annotations

from xime.core.exception.framework import XimeException

# Modbus exception codes defined by the application protocol. The device sends
# only the number, which on its own tells an operator nothing.
# Thiết bị chỉ gửi con số - tự nó không nói lên điều gì với người vận hành.
EXCEPTION_CODE_MEANINGS: dict[int, str] = {
    1: "ILLEGAL FUNCTION - the device does not support this function code",
    2: "ILLEGAL DATA ADDRESS - the address (or part of the range) does not "
       "exist on this device",
    3: "ILLEGAL DATA VALUE - the value or the quantity requested is out of range",
    4: "SLAVE DEVICE FAILURE - an unrecoverable error occurred on the device",
    5: "ACKNOWLEDGE - the request was accepted but needs a long time to process",
    6: "SLAVE DEVICE BUSY - the device is busy; retry later",
    8: "MEMORY PARITY ERROR",
    10: "GATEWAY PATH UNAVAILABLE - the gateway cannot reach the target unit id",
    11: "GATEWAY TARGET DEVICE FAILED TO RESPOND - wrong unit id, or the device "
        "behind the gateway is offline",
}


class ModbusError(XimeException):
    """Base class for every Modbus adapter failure."""


class ModbusConnectionError(ModbusError):
    """The device could not be reached, or the connection dropped mid-request."""


class ModbusDeviceError(ModbusError):
    """The device answered with a Modbus exception response.

    Carries the raw `code` so callers can branch on it, and expands the code
    into words in the message because the number alone is meaningless in a log.
    """

    def __init__(self, code: int | None, detail: str = "") -> None:
        self.code = code
        meaning = EXCEPTION_CODE_MEANINGS.get(code or 0, "unknown exception code")
        message = f"Modbus exception {code}: {meaning}"
        if detail:
            message = f"{message} ({detail})"
        super().__init__(message)


class ModbusCodecError(ModbusError, ValueError):
    """A value cannot be decoded from, or encoded into, its field."""
