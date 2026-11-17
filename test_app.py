"""test_app.py —— 用 Streamlit 官方的 AppTest 跑界面冒烟测试。

直接运行脚本，不用开浏览器：
    python test_app.py
    python test_app.py --with-ai    # 改写那段真调 DeepSeek

覆盖：首屏、空输入、多条体检、全合规、填入示例、改写路径。
"""

from __future__ import annotations

import os
import sys

from streamlit.testing.v1 import AppTest

import check as core

SAMPLE_LINES = 4
SAMPLE_HITS = 11          # 示例 4 条文案的命中总数
SAMPLE_RISKY = 3          # 其中命中的条数
CLEAN = "这款月季含7天绿植险，秋季盛花，具体以详情页为准"


def _text_of(elements) -> str:
    return "\n".join(str(getattr(e, "value", "") or "") for e in elements)


def run(use_ai: bool) -> int:
    failures = 0

    def report(name: str, ok: bool, detail: str = "") -> None:
        nonlocal failures
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  {name}{('  -> ' + detail) if detail and not ok else ''}")

    # --- 1. 首屏 ---
    at = AppTest.from_file("app.py", default_timeout=120).run()
    report("首屏无异常", not at.exception, _text_of(at.exception))
    body = _text_of(at.markdown)
    report("标题渲染（渐变 Hero）", "花木口播文案合规校验" in body)
    report("两个标签页", len(at.tabs) == 2, f"实际 {len(at.tabs)}")

    # --- 2. 空输入 ---
    at.button[0].click().run()
    report("空输入提示", any("请先粘贴" in str(w.value) for w in at.warning))

    # --- 3. 多条 + 只体检 ---
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.text_area(key="bulk_text").set_value(
        "家人们看这棵桂花，四季开花，养死包赔，全网最低价！\n"
        "这款月季包开花，招财辟邪，还能降血压，30天发芽！\n"
        "南北方均可种植，浇水就活，所见即所得"
    ).run()
    at.checkbox[0].set_value(True).run()
    at.button[0].click().run()
    report("多条体检无异常", not at.exception, _text_of(at.exception))
    metrics = [str(m.value) for m in at.metric]
    report(
        "统计正确（3 条 / 11 命中 / 3 需处理 / 最高 极高）",
        metrics[:4] == ["3", "11", "3", "极高"],
        f"metrics={metrics}",
    )
    report("出现逐条结果", "逐条结果" in _text_of(at.markdown))
    report("只体检时提示跳过改写", any("跳过" in str(c.value) for c in at.caption))

    # --- 4. 全合规 ---
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.text_area(key="bulk_text").set_value(CLEAN).run()
    at.button[0].click().run()
    report("全合规提示", any("未命中硬规则" in str(s.value) for s in at.success))

    # --- 5. 填入示例（回调）---
    at = AppTest.from_file("app.py", default_timeout=120).run()
    for btn in at.button:
        if "填入示例" in btn.label:
            btn.click().run()
            break
    report("填入示例无异常", not at.exception, _text_of(at.exception))
    filled = at.text_area(key="bulk_text").value or ""
    report("填入示例后为 4 行", len([ln for ln in filled.splitlines() if ln.strip()]) == SAMPLE_LINES,
           f"实际 {len(filled.splitlines())} 行")

    # --- 6. 改写路径 ---
    original = core.rewrite_with_deepseek
    if use_ai:
        at = AppTest.from_file("app.py", default_timeout=400).run()
    else:
        core.rewrite_with_deepseek = lambda text, hits, **kw: (
            "【逐条说明】\n- 测试桩，不调用模型。\n\n【改写文案】\n家人们看这棵桂花，含7天绿植险（以详情页为准）。"
        )
        at = AppTest.from_file("app.py", default_timeout=200).run()
    try:
        at.text_area(key="bulk_text").set_value(
            "家人们看这棵桂花，四季开花，养死包赔，全网最低价！"
        ).run()
        at.button[0].click().run()
    finally:
        core.rewrite_with_deepseek = original

    report("改写路径无异常", not at.exception, _text_of(at.exception))
    body = _text_of(at.markdown) + _text_of(at.code)
    report("出现合规改写区块", "合规改写" in body or "7天绿植险" in body, body[:120])

    print(f"\n界面自检：{'全部通过' if failures == 0 else f'{failures} 项失败'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    code = run(use_ai="--with-ai" in sys.argv)
    sys.stdout.flush()
    sys.stderr.flush()
    # 直接退出：Streamlit/Tempfile 在 Windows 沙箱里退出阶段清理临时目录会抛
    # PermissionError，把退出码盖成 1，让 CI 误判失败
    os._exit(code)
