# pairwise-pngkit

## 题面（可直接粘贴）

素材校验改成流式后误放行：分片喂入与整包结果不一致，出错后校验器不能复用，tRNS 两种形态在跨分片时错位，未知关键块被静默忽略。pngkit/core.py 是核心，tests/test_core.py 15 个红。要修的是：任意分片与整包校验一致；出错 reset 后可复用；IHDR 必须第一；未知关键块抛 ValueError；tRNS 灰度 2 字节、RGB 6 字节；签名、CRC、位深、色型、截断都要报错。

## 运行方式

```bash
python -m pytest tests -q
```

初始结果应为 `15 failed`（全部因 `NotImplementedError` 失败，无 collection error）。

## 字段

- 所属领域：游戏、图形与多媒体
- 子方向：图像处理
- 任务类型：Bugfix
- 语言/框架：Python 3, pytest
- 环境可复现等级：无外部依赖
