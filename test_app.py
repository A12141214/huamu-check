"""test_app.py —— 用 Streamlit 官方的 AppTest 跑界面冒烟测试。

直接运行脚本，不用开浏览器：
    python test_app.py

覆盖：首屏渲染、空输入告警、只体检（不调模型）、命中渲染、模型改写路径
（`--with-ai` 才会真的调 DeepSeek，默认用桩函数，不花钱）。
"""

from __future__ import annotations

import os
import sys

from streamlit.testing.v1 import AppTest

import check as core

SAMPLE = "家人们看这棵桂花，四季开花，养死包赔，全网最低价，喜欢的赶紧下单！"
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
    report("标题渲染", any("花木口播文案合规校验" in str(t.value) for t in at.title))
    report("三个标签页", len(at.tabs) == 3, f"实际 {len(at.tabs)}")

    # --- 2. 空输入 ---
    at.button[0].click().run()
    report("空输入提示", any("请先粘贴" in str(w.value) for w in at.warning))

    # --- 3. 只体检，不调模型 ---
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.text_area(key="single_text").set_value(SAMPLE).run()
    at.checkbox[0].set_value(True).run()
    at.button[0].click().run()
    report("只体检无异常", not at.exception, _text_of(at.exception))
    metrics = [str(m.value) for m in at.metric]
    report("命中数为 3", metrics[:2] == ["3", "极高"], f"metrics={metrics}")
    report("逐条命中卡片", len(at.expander) >= 3, f"expander={len(at.expander)}")
    report("只体检不调模型", any("跳过模型改写" in str(c.value) for c in at.caption))

    # --- 4. 合规文案：命中 0 条，不调模型 ---
    at = AppTest.from_file("app.py", default_timeout=120).run()
    at.text_area(key="single_text").set_value(CLEAN).run()
    at.button[0].click().run()
    report("合规稿命中 0 条", any("未命中硬规则" in str(s.value) for s in at.success))

    # --- 5. 改写路径 ---
    if use_ai:
        at = AppTest.from_file("app.py", default_timeout=300).run()
        at.text_area(key="single_text").set_value(SAMPLE).run()
        at.button[0].click().run()
    else:
        original = core.rewrite_with_deepseek
        core.rewrite_with_deepseek = lambda text, hits, **kw: (
            "【逐条说明】\n- R001（极高）：测试桩，不调用模型。\n\n【改写文案】\n家人们看这棵桂花，含7天绿植险（以详情页为准）。"
        )
        try:
            at = AppTest.from_file("app.py", default_timeout=120).run()
            at.text_area(key="single_text").set_value(SAMPLE).run()
            at.button[0].click().run()
        finally:
            core.rewrite_with_deepseek = original

    report("改写路径无异常", not at.exception, _text_of(at.exception))
    body = _text_of(at.markdown) + _text_of(at.text_area)
    report("出现改写区块", "逐条说明" in body and "改写文案" in body)
    report("可编辑改写稿已填充", "7天绿植险" in _text_of(at.text_area), _text_of(at.text_area)[:80])

    print(f"\n界面自检：{'全部通过' if failures == 0 else f'{failures} 项失败'}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    code = run(use_ai="--with-ai" in sys.argv)
    sys.stdout.flush()
    sys.stderr.flush()
    # 直接退出：Streamlit/Tempfile 在 Windows 沙箱里退出阶段清理临时目录会抛
    # PermissionError，把退出码盖成 1，让 CI 误判失败
    os._exit(code)
