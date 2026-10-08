"""An image's width and height from its header, by the standard library only: whether
read_artifact may show it to the model (lado.artifacts, IMAGE_MAX_SIDE)."""

import struct

# JPEG's start-of-frame markers, which carry the size: SOF0-SOF15 but DHT (C4), JPG (C8)
# and DAC (CC).
_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


def size(data: bytes, media_type: str) -> tuple[int, int] | None:
    """(width, height) of a PNG, GIF, WebP or JPEG of `media_type`; None when its header
    cannot be read as that format, or for any other type."""
    reader = {"image/png": _png, "image/gif": _gif, "image/webp": _webp, "image/jpeg": _jpeg}
    try:
        return reader[media_type](data) if media_type in reader else None
    except (struct.error, IndexError):
        return None


def _png(data: bytes) -> tuple[int, int] | None:
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return struct.unpack(">II", data[16:24])


def _gif(data: bytes) -> tuple[int, int] | None:
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        return None
    return struct.unpack("<HH", data[6:10])


def _webp(data: bytes) -> tuple[int, int] | None:
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return None
    chunk, payload = data[12:16], data[20:]
    if chunk == b"VP8 ":  # lossy: after the frame tag and start code, 14 bits each
        if payload[3:6] != b"\x9d\x01\x2a":
            return None
        width, height = struct.unpack("<HH", payload[6:10])
        return width & 0x3FFF, height & 0x3FFF
    if chunk == b"VP8L":  # lossless: after the signature, 14 bits each, minus one
        if payload[:1] != b"\x2f":
            return None
        (bits,) = struct.unpack("<I", payload[1:5])
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if chunk == b"VP8X":  # extended: the canvas, 24 bits each, minus one
        if len(payload) < 10:
            return None
        return int.from_bytes(payload[4:7], "little") + 1, int.from_bytes(
            payload[7:10], "little"
        ) + 1
    return None


def _jpeg(data: bytes) -> tuple[int, int] | None:
    if data[:2] != b"\xff\xd8":
        return None
    at = 2
    while at + 4 <= len(data):
        if data[at] != 0xFF:
            return None
        marker = data[at + 1]
        if marker == 0xFF:  # fill byte
            at += 1
            continue
        if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:  # no length
            at += 2
            continue
        if marker in (0xD9, 0xDA):  # the end, or the scan: no frame header before it
            return None
        (length,) = struct.unpack(">H", data[at + 2 : at + 4])
        if at + 2 + length > len(data):  # cut: the segment runs past the end
            return None
        if marker in _SOF:
            height, width = struct.unpack(">HH", data[at + 5 : at + 9])
            return width, height
        at += 2 + length
    return None
