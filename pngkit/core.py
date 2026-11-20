"""pngkit 核心 API：流式 PNG 校验器。

任意分片喂入与整包喂入结果一致；出错后 reset() 可复用。
"""

import struct
import zlib

_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# 每种色型允许的位深（PNG 规范）
_ALLOWED_DEPTH = {
    0: {1, 2, 4, 8, 16},  # 灰度
    2: {8, 16},           # RGB
    3: {1, 2, 4, 8},      # 调色板
    4: {8, 16},           # 灰度+alpha
    6: {8, 16},           # RGBA
}

_KNOWN_CRITICAL = {b"IHDR", b"PLTE", b"IDAT", b"IEND"}


class PngValidator:
    def __init__(self):
        """构造校验器"""
        self.reset()

    def reset(self):
        """清空状态，校验器可复用"""
        self._buf = bytearray()
        self._sig_ok = False
        self._seen_ihdr = False
        self._seen_iend = False
        self._chunks = []
        self._trns = None
        self._color = None
        self._depth = None
        self._error = None

    def feed(self, data):
        """喂入字节（任意分片）；解析错误延迟到 validate() 抛出"""
        if self._error is not None or self._seen_iend:
            return  # 已出错或已结束的字节忽略
        self._buf += bytes(data)
        try:
            self._process()
        except ValueError as exc:
            self._error = exc

    def validate(self):
        """结束并校验，完整合法返回 True，否则抛 ValueError"""
        if self._error is not None:
            raise self._error
        if not self._sig_ok:
            raise ValueError("数据截断：PNG 签名不完整")
        if not self._seen_ihdr:
            raise ValueError("数据截断：缺少 IHDR")
        if not self._seen_iend:
            raise ValueError("数据截断：缺少 IEND")
        return True

    def chunks(self):
        """已识别块（按出现顺序的类型名列表）"""
        return list(self._chunks)

    def trns(self):
        """返回 tRNS 解析结果：灰度 (g,)，RGB (r, g, b)，调色板 (a0, a1, ...)"""
        return self._trns

    # ---- 内部实现 ----

    def _process(self):
        if not self._sig_ok:
            if len(self._buf) < 8:
                return
            if bytes(self._buf[:8]) != _SIGNATURE:
                raise ValueError("PNG 签名错误")
            del self._buf[:8]
            self._sig_ok = True
        while not self._seen_iend:
            if len(self._buf) < 8:
                return
            (length,) = struct.unpack(">I", self._buf[:4])
            ctype = bytes(self._buf[4:8])
            if len(self._buf) < 8 + length + 4:
                return  # 等更多分片
            payload = bytes(self._buf[8:8 + length])
            (crc,) = struct.unpack(">I", self._buf[8 + length:12 + length])
            del self._buf[:12 + length]
            if zlib.crc32(ctype + payload) & 0xFFFFFFFF != crc:
                raise ValueError("块 %r 的 CRC 校验失败" % ctype)
            self._handle(ctype, payload)
        self._buf.clear()

    def _handle(self, ctype, payload):
        if not self._seen_ihdr:
            if ctype != b"IHDR":
                raise ValueError("IHDR 必须是第一个块，实际为 %r" % ctype)
            self._parse_ihdr(payload)
            self._seen_ihdr = True
            self._chunks.append("IHDR")
            return
        if ctype == b"IHDR":
            raise ValueError("重复的 IHDR 块")
        critical = not (ctype[0] & 0x20)  # 首字母大写 = 关键块
        if critical and ctype not in _KNOWN_CRITICAL:
            raise ValueError("未知关键块 %r" % ctype)
        if ctype == b"IEND":
            if payload:
                raise ValueError("IEND 块必须为空")
            self._seen_iend = True
        elif ctype == b"tRNS":
            self._parse_trns(payload)
        self._chunks.append(ctype.decode("latin1"))

    def _parse_ihdr(self, payload):
        if len(payload) != 13:
            raise ValueError("IHDR 长度必须为 13 字节")
        w, h, depth, color, comp, filt, inter = struct.unpack(">IIBBBBB", payload)
        if w == 0 or h == 0:
            raise ValueError("宽高不能为 0")
        if color not in _ALLOWED_DEPTH:
            raise ValueError("非法色型 %d" % color)
        if depth not in _ALLOWED_DEPTH[color]:
            raise ValueError("色型 %d 不允许位深 %d" % (color, depth))
        if comp != 0 or filt != 0:
            raise ValueError("非法压缩/过滤方式")
        if inter not in (0, 1):
            raise ValueError("非法隔行方式 %d" % inter)
        self._color = color
        self._depth = depth

    def _parse_trns(self, payload):
        if self._color == 0:  # 灰度：2 字节
            if len(payload) != 2:
                raise ValueError("灰度 tRNS 必须为 2 字节")
            self._trns = (struct.unpack(">H", payload)[0],)
        elif self._color == 2:  # RGB：6 字节
            if len(payload) != 6:
                raise ValueError("RGB tRNS 必须为 6 字节")
            self._trns = struct.unpack(">HHH", payload)
        elif self._color == 3:  # 调色板：每入口 1 字节 alpha
            self._trns = tuple(payload)
        else:
            raise ValueError("色型 %d 不允许 tRNS 块" % self._color)
