"""Small KW1281 reader for an echoing FTDI KKL cable and engine address 01."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

ENGINE = 0x01
ACK = 0x09
NAK = 0x0A
IDENT = 0xF6
FAULTS = 0xFC
MEASURED = 0xE7
END = 0x06
READ_FAULTS = 0x07
READ_GROUP = 0x29
ALLOWED_GROUPS = (1, 3, 7, 11, 12)
MAX_BLOCKS = 32


class LinkError(Exception):
    """The cable or controller failed to complete the expected exchange."""


class SerialPort(Protocol):
    break_condition: bool

    def reset_input_buffer(self) -> None: ...
    def read(self, size: int = 1) -> bytes: ...
    def write(self, data: bytes) -> int: ...


@dataclass(frozen=True)
class Block:
    counter: int
    title: int
    data: bytes


def address_bits(address: int) -> tuple[int, ...]:
    data = tuple((address >> bit) & 1 for bit in range(7))
    odd_parity_bit = 1 - (sum(data) % 2)
    return (0, *data, odd_parity_bit, 1)


class KLine:
    """Byte I/O over a transparent cable that echoes each transmitted byte."""

    def __init__(
        self,
        serial: SerialPort,
        byte_delay_ms: int = 5,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.serial = serial
        self.byte_delay = byte_delay_ms / 1000
        self.sleep = sleep
        self.clock = clock

    def slow_init(self) -> None:
        self.serial.break_condition = False
        self.sleep(0.350)
        start = self.clock()
        previous = 1
        try:
            # The UART is already at the data rate. BREAK holds TX low.
            for index, bit in enumerate(address_bits(ENGINE)):
                remaining = start + index * 0.200 - self.clock()
                if remaining > 0:
                    self.sleep(remaining)
                if bit != previous:
                    self.serial.break_condition = bit == 0
                    previous = bit
        finally:
            if previous == 0:
                self.serial.break_condition = False
        # BREAK can leave framing bytes in the cable's RX buffer. Purge early
        # in the stop bit, so a fast ECU response is not purged with them.
        self.sleep(0.030)
        self.serial.reset_input_buffer()

    def read(self, stage: str) -> int:
        result = self.serial.read(1)
        if len(result) != 1:
            raise LinkError(f"Timed out waiting for {stage}.")
        return result[0]

    def write(self, byte: int) -> None:
        if self.serial.write(bytes((byte,))) != 1:
            raise LinkError("The serial port did not accept a full byte.")
        echo = self.read(f"cable echo for 0x{byte:02X}")
        if echo != byte:
            raise LinkError(f"Bad cable echo: sent 0x{byte:02X}, received 0x{echo:02X}.")

    def expect(self, byte: int, stage: str) -> None:
        result = self.read(stage)
        if result != byte:
            raise LinkError(f"Expected 0x{byte:02X} for {stage}, received 0x{result:02X}.")

    def answer_keywords(self) -> tuple[int, int]:
        first = self.read("keyword 1")
        second = self.read("keyword 2")
        protocol = ((second & 0x7F) << 7) | (first & 0x7F)
        if protocol != 1281:
            raise LinkError(f"Received keywords {first:02X} {second:02X} (protocol {protocol}).")
        self.sleep(0.027)
        self.write(second ^ 0xFF)
        return first, second


class EngineSession:
    """Send only identity handshake, fault reads, group reads and session framing."""

    def __init__(self, link: KLine) -> None:
        self.link = link
        self.counter: int | None = None
        self.keywords: tuple[int, int] | None = None

    def connect(self) -> list[str]:
        self.link.slow_init()
        self.link.expect(0x55, "the wake-up sync byte")
        self.keywords = self.link.answer_keywords()

        identification = []
        for index in range(MAX_BLOCKS):
            block = self._receive(first_identification=index == 0)
            if block.title == ACK and not block.data and identification:
                return identification
            if block.title != IDENT or not block.data:
                raise LinkError(f"Unexpected ECU identification block 0x{block.title:02X}.")
            if block.data[0] != 0:  # The binary coding/workshop block starts with zero.
                printable = "".join(chr(byte & 0x7F) for byte in block.data)
                cleaned = "".join(char if 32 <= ord(char) <= 126 else " " for char in printable)
                if cleaned.strip():
                    identification.append(cleaned.strip())
            self._send(ACK)
        raise LinkError("ECU identification exceeded the block limit.")

    def read_faults(self) -> tuple[str, list[dict]]:
        """Return status plus complete records. FF FF 88 is the empty response."""
        self._send(READ_FAULTS)
        received_fault_block = False
        faults = []
        for _ in range(MAX_BLOCKS):
            block = self._receive()
            if block.title == ACK and not block.data:
                return ("read" if received_fault_block else "unavailable"), faults
            if block.title == NAK and not block.data and not received_fault_block:
                return "unavailable", []
            if block.title != FAULTS or not block.data or len(block.data) % 3:
                raise LinkError("Unexpected or incomplete fault-memory response.")
            empty = block.data == b"\xff\xff\x88" and not received_fault_block
            if not empty:
                for high, low, status in zip(block.data[::3], block.data[1::3], block.data[2::3]):
                    if high == low == 0xFF:
                        raise LinkError("Unexpected fault-memory sentinel inside a fault list.")
                    faults.append({"code": f"{(high << 8) | low:05d}", "status_hex": f"{status:02X}"})
            received_fault_block = True
            self._send(ACK)
        raise LinkError("Fault memory exceeded the block limit.")

    def read_group(self, group: int) -> Block:
        if group not in ALLOWED_GROUPS:
            raise ValueError(f"Unsupported group {group}.")
        self._send(READ_GROUP, bytes((group,)))
        response = self._receive()
        if response.title == MEASURED and response.data and len(response.data) % 3 == 0:
            return response
        if response.title in (ACK, NAK) and not response.data:
            return response
        # Some KW1281 modules use other data encodings. Preserve the payload
        # for inspection without applying the E7 scaling rules to it.
        if response.title in (0x02, 0xF4) and response.data:
            return response
        raise LinkError(f"Unexpected or malformed response 0x{response.title:02X} for group {group:03d}.")

    def close(self) -> None:
        self._send(END)

    def _send(self, title: int, data: bytes = b"") -> None:
        if title == READ_GROUP:
            if len(data) != 1 or data[0] not in ALLOWED_GROUPS:
                raise ValueError("Group request must use an allowed group.")
        elif title not in (ACK, END, READ_FAULTS) or data:
            raise ValueError("The request is outside the read-only protocol subset.")
        if self.counter is None:
            raise LinkError("ECU has not started a session.")
        self.link.sleep(0.025)
        for byte in bytes((len(data) + 3, self.counter, title)) + data:
            self.link.write(byte)
            self.link.expect(byte ^ 0xFF, f"ECU complement for 0x{byte:02X}")
            self.link.sleep(self.link.byte_delay)
        self.link.write(0x03)
        self.counter = (self.counter + 1) & 0xFF

    def _receive(self, *, first_identification: bool = False) -> Block:
        length = self.link.read("block length")
        if first_identification:
            for _ in range(2):
                if length != 0x55:
                    break
                self.link.answer_keywords()
                length = self.link.read("block length after repeated sync")
            if length == 0x55:
                raise LinkError("The ECU repeated its wake-up response.")
        if length < 3:
            raise LinkError(f"Invalid block length {length}.")
        self._ack_byte(length)
        counter = self.link.read("block counter")
        if self.counter is not None and counter != self.counter:
            raise LinkError(f"Expected block counter 0x{self.counter:02X}, received 0x{counter:02X}.")
        self._ack_byte(counter)
        title = self._receive_byte()
        data = bytes(self._receive_byte() for _ in range(length - 3))
        self.link.expect(0x03, "block terminator")
        self.counter = (counter + 1) & 0xFF
        return Block(counter, title, data)

    def _receive_byte(self) -> int:
        byte = self.link.read("block byte")
        self._ack_byte(byte)
        return byte

    def _ack_byte(self, byte: int) -> None:
        self.link.sleep(self.link.byte_delay)
        self.link.write(byte ^ 0xFF)
