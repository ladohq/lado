"""An image's width and height from its header (lado.images), built here by each format's
spec: PNG IHDR, GIF logical screen, WebP VP8/VP8L/VP8X, JPEG SOFn."""

import struct
import zlib

import pytest

from lado import images


def png(width, height):
    """A whole PNG of one grey pixel row per line, as a browser would read it."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    rows = b"".join(b"\x00" + b"\x80" * width for _ in range(height))

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def gif(width, height):
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00\x00\x00;"


def webp(chunk, payload):
    body = b"WEBP" + chunk + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(body)) + body


def vp8(width, height):
    # frame tag (3 bytes), start code, then 14 bits of width and of height (2 bits scale)
    return webp(
        b"VP8 ", b"\x00\x00\x00\x9d\x01\x2a" + struct.pack("<HH", width, height) + b"\x00" * 4
    )


def vp8l(width, height):
    bits = (width - 1) | ((height - 1) << 14)
    return webp(b"VP8L", b"\x2f" + struct.pack("<I", bits) + b"\x00" * 4)


def vp8x(width, height):
    w, h = (width - 1).to_bytes(3, "little"), (height - 1).to_bytes(3, "little")
    return webp(b"VP8X", b"\x00\x00\x00\x00" + w + h)


def jpeg(width, height, sof=0xC0):
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    frame = struct.pack(">BHHB", 8, height, width, 3) + b"\x01\x22\x00\x02\x11\x01\x03\x11\x01"
    sofn = bytes([0xFF, sof]) + struct.pack(">H", len(frame) + 2) + frame
    return b"\xff\xd8" + app0 + sofn + b"\xff\xda\x00\x02" + b"\x00" * 8 + b"\xff\xd9"


@pytest.mark.parametrize(
    "media_type, data, size",
    [
        ("image/png", png(3, 2), (3, 2)),
        ("image/gif", gif(640, 480), (640, 480)),
        ("image/webp", vp8(1920, 1080), (1920, 1080)),
        ("image/webp", vp8l(2880, 1800), (2880, 1800)),
        ("image/webp", vp8x(8001, 20), (8001, 20)),
        ("image/jpeg", jpeg(1024, 768), (1024, 768)),
        ("image/jpeg", jpeg(4032, 3024, sof=0xC2), (4032, 3024)),  # progressive
    ],
)
def test_the_size_is_read_from_the_header(media_type, data, size):
    assert images.size(data, media_type) == size


@pytest.mark.parametrize(
    "media_type, data",
    [
        ("image/png", png(3, 2)[:20]),  # cut in IHDR
        ("image/png", b"\x89PNG"),
        ("image/png", gif(1, 1)),  # another format than its type
        ("image/gif", b"GIF89"),
        ("image/webp", b"RIFF\x00\x00\x00\x00WEBPVP8 "),
        ("image/webp", webp(b"ALPH", b"\x00" * 10)),
        ("image/jpeg", jpeg(10, 10)[:30]),  # no SOFn before the end
        ("image/jpeg", b"\xff\xd8\xff\xe0\xff\xff"),  # a segment longer than the file
        ("image/jpeg", b""),
        ("application/pdf", b"%PDF-1.7"),
    ],
)
def test_a_header_that_cannot_be_read_gives_none(media_type, data):
    assert images.size(data, media_type) is None
