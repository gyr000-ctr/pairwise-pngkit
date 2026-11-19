import math
import struct
import threading
import zlib

import pytest

import pngkit

def _raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    return False

SIG = b"\x89PNG\r\n\x1a\n"


def _chunk(t, payload):
    return struct.pack(">I", len(payload)) + t + payload + struct.pack(">I", zlib.crc32(t + payload) & 0xFFFFFFFF)


def _ihdr(w=1, h=1, depth=8, color=0):
    return _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, depth, color, 0, 0, 0))


def _png(*chs):
    return SIG + b"".join(chs)


def _valid():
    return _png(_ihdr(), _chunk(b"IEND", b""))


def _whole(data):
    v = pngkit.PngValidator()
    v.feed(data)
    return v.validate()


def _split(data, n):
    v = pngkit.PngValidator()
    for i in range(0, len(data), n):
        v.feed(data[i:i + n])
    return v.validate()


def _same(n):
    return _split(_valid(), n) == _whole(_valid())


def _bad_crc_bytes():
    bad = bytearray(_valid())
    bad[-16] ^= 0xFF
    return bytes(bad)


def _reset_after_error():
    v = pngkit.PngValidator()
    v.feed(_bad_crc_bytes())
    ok = _raises(v.validate)
    v.reset()
    v.feed(_valid())
    return ok and v.validate() is True


def _trns_gray():
    v = pngkit.PngValidator()
    v.feed(_png(_ihdr(), _chunk(b"tRNS", b"\x00\x05"), _chunk(b"IEND", b"")))
    v.validate()
    return v.trns() == (5,)


def _trns_rgb():
    v = pngkit.PngValidator()
    v.feed(_png(_ihdr(color=2), _chunk(b"tRNS", b"\x00\x01\x00\x02\x00\x03"), _chunk(b"IEND", b"")))
    v.validate()
    return v.trns() == (1, 2, 3)


def _chunks_count():
    v = pngkit.PngValidator()
    v.feed(_valid())
    v.validate()
    return len(v.chunks()) == 2

CASES = [
        ("split1", lambda: _same(1)),
        ("split4", lambda: _same(4)),
        ("split9", lambda: _same(9)),
        ("bad_crc", lambda: _raises(lambda: _whole(_bad_crc_bytes()))),
        ("reset_reuse", lambda: _reset_after_error()),
        ("missing_iend", lambda: _raises(lambda: _whole(_png(_ihdr())))),
        ("ihdr_not_first", lambda: _raises(lambda: _whole(_png(_chunk(b"tEXt", b"a\x00b"), _ihdr(), _chunk(b"IEND", b""))))),
        ("trns_gray", lambda: _trns_gray()),
        ("trns_rgb", lambda: _trns_rgb()),
        ("unknown_critical", lambda: _raises(lambda: _whole(_png(_ihdr(), _chunk(b"ZZZZ", b""), _chunk(b"IEND", b""))))),
        ("unknown_ancillary", lambda: _whole(_png(_ihdr(), _chunk(b"tEXt", b"a\x00b"), _chunk(b"IEND", b""))) is True),
        ("bad_signature", lambda: _raises(lambda: _whole(b"not a png"))),
        ("bad_depth", lambda: _raises(lambda: _whole(_png(_ihdr(depth=3), _chunk(b"IEND", b""))))),
        ("bad_color", lambda: _raises(lambda: _whole(_png(_ihdr(color=1), _chunk(b"IEND", b""))))),
        ("chunks", lambda: _chunks_count()),
    ]


@pytest.mark.parametrize("name,check", CASES, ids=[c[0] for c in CASES])
def test_spec(name, check):
    assert check() is True
