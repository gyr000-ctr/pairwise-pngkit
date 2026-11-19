"""pngkit 核心 API（初始未实现）。"""


class PngValidator:
    def __init__(self):
        """构造校验器"""
        raise NotImplementedError

    def feed(self, data):
        """喂入字节"""
        raise NotImplementedError

    def validate(self):
        """结束并校验"""
        raise NotImplementedError

    def chunks(self):
        """已识别块"""
        raise NotImplementedError

    def trns(self):
        """返回 tRNS 解析结果"""
        raise NotImplementedError

    def reset(self):
        """清空状态"""
        raise NotImplementedError
