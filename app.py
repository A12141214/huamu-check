"""app.py —— 花木口播文案合规校验（Streamlit 网页版）。

界面层只负责展示；规则匹配、替换分组、模型改写全部复用 check.py，
避免两份逻辑各改各的、线上和本地结果不一致。

本地运行：
    streamlit run app.py

Streamlit Community Cloud 部署：上传 app.py / check.py / rules.json /
replacements.json / requirements.txt，API Key 写在 Secrets 里。
"""

from __future__ import annotations

import html
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check as core  # noqa: E402  - 复用检测/改写逻辑，这里不重复实现

RISK_BADGE = {"极高": "🔴", "高": "🟠", "中": "🟡", "低": "🟢"}

st.set_page_config(
    page_title="花木口播文案合规校验",
    page_icon="🌿",
    layout="wide",
)


# ========== 资源与配置 ==========
# 故意不加 @st.cache_resource：rules.json 只有 3KB，每次 rerun 重读的代价可以忽略，
# 而加缓存会导致「改了 JSON 刷新页面却不生效」，运营会以为规则坏了。
def load_rules() -> list[dict]:
    return core.load_rules()


def load_replacements() -> dict:
    return core.load_replacements()


def get_api_key() -> str | None:
    """优先级：侧栏临时填写 > Streamlit Secrets > 环境变量 / .env。

    侧栏那个是给「找不到 Secrets 菜单」时兜底用的：只存在浏览器会话里，
    不落盘、不进仓库，刷新页面需要重填。
    """
    tmp = (st.session_state.get("tmp_key") or "").strip()
    if tmp:
        return tmp
    try:
        if "DEEPSEEK_API_KEY" in st.secrets:  # type: ignore[attr-defined]
            key = str(st.secrets["DEEPSEEK_API_KEY"]).strip()  # type: ignore[attr-defined]
            if key:
                return key
    except Exception:
        # 没有 secrets.toml 时 st.secrets 会抛异常，本地跑属于正常情况
        pass
    core._load_dotenv()
    return (os.getenv("DEEPSEEK_API_KEY") or "").strip() or None


# ========== 展示辅助 ==========
def merge_spans(hits: list[dict]) -> list[tuple[int, int]]:
    """合并重叠命中，避免同一段文字被重复高亮。"""
    spans = sorted((h["start"], h["end"]) for h in hits)
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def highlight(text: str, hits: list[dict]) -> str:
    """把命中片段标红，商家一眼能在原稿里定位。"""
    parts: list[str] = []
    cursor = 0
    for start, end in merge_spans(hits):
        parts.append(html.escape(text[cursor:start]))
        parts.append(
            '<mark style="background:#ffd8d8;color:#a40000;padding:0 3px;'
            f'border-radius:4px;font-weight:600;">{html.escape(text[start:end])}</mark>'
        )
        cursor = end
    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def split_advice(advice: str) -> tuple[str, str]:
    """把模型输出拆成「逐条说明」和「改写文案」两块。"""
    if "【改写文案】" not in advice:
        return advice.strip(), ""
    head, tail = advice.split("【改写文案】", 1)
    head = head.replace("【逐条说明】", "").strip()
    return head, tail.strip()


def top_risk(hits: list[dict]) -> str:
    return hits[0]["risk"] if hits else "无"


# ========== 页面 ==========
rules = load_rules()
replacements = load_replacements()

st.title("🌿 花木口播文案合规校验")
st.caption(
    f"粘贴抖音花木口播文案 → 扫 {len(rules)} 条硬红线 → 命中后给出依据与合规改写。"
    "未命中不调用模型、不计费。"
)

# 配置自检：云端 Secrets 写错键名/没保存，从界面上就能看出来，不用靠猜
with st.sidebar:
    st.subheader("配置自检")
    try:
        secret_names = list(st.secrets.keys())  # type: ignore[attr-defined]
    except Exception:
        secret_names = []
    st.caption("Secrets 键：" + ("、".join(secret_names) if secret_names else "（没有读到任何键）"))
    st.caption("API Key：" + ("✅ 已读取" if get_api_key() else "❌ 未配置"))

    if not get_api_key():
        st.text_input(
            "临时 API Key（不保存，可随时撤回）",
            type="password",
            key="tmp_key",
            placeholder="sk-...",
            help="填在这里只对当前浏览器会话有效：不写入磁盘、不进仓库，刷新页面即失效。"
            "长期使用请配到 Settings → Secrets。",
        )
    st.divider()
    st.caption(
        "云端配置路径：应用页 `⋮` → `Settings` → `Secrets`，"
        '内容为 `DEEPSEEK_API_KEY = "sk-..."`，保存后应用会自动重启。'
    )

SAMPLE = "家人们看这棵桂花，四季开花，养死包赔，全网最低价，喜欢的赶紧下单！"


def _fill_sample() -> None:
    """按钮回调里改 session_state 是安全的（此时 widget 还没重新实例化）。"""
    st.session_state["single_text"] = SAMPLE
    st.session_state.pop("result", None)


tab_single, tab_batch, tab_rules = st.tabs(["单条校验", "批量体检（不调模型）", "规则库"])

# ---------- 单条校验 ----------
with tab_single:
    left, right = st.columns([3, 2], gap="large")

    with left:
        text = st.text_area(
            "口播文案",
            height=180,
            placeholder=f"例：{SAMPLE}",
            key="single_text",
            label_visibility="collapsed",
        )
        col_run, col_sample, col_skip = st.columns([2, 1, 2])
        run = col_run.button("开始校验", type="primary", use_container_width=True)
        # 必须用 on_click 回调：脚本跑起来之后不能再改已有 widget 的 session_state，
        # 直接赋值会抛 StreamlitWidgetAlreadyInstantiatedError。
        col_sample.button("填入示例", use_container_width=True, on_click=_fill_sample)
        rule_only = col_skip.checkbox("只做规则体检（不调模型）", value=False)

        if run:
            if not text.strip():
                st.warning("请先粘贴一段文案。")
                st.session_state.pop("result", None)
            elif rule_only:
                st.session_state["result"] = {
                    "text": text.strip(),
                    "hits": core.lint(text, rules),
                    "advice": None,
                    "rewritten": False,
                }
            else:
                key = get_api_key()
                hits = core.lint(text, rules)
                if not hits:
                    # 没命中就不调模型：省钱，也避免模型把合规稿改坏
                    st.session_state["result"] = {
                        "text": text.strip(),
                        "hits": [],
                        "advice": None,
                        "rewritten": False,
                    }
                elif not key:
                    st.error(
                        "未配置 DEEPSEEK_API_KEY。本地请在项目根目录 `.env` 写 "
                        "`DEEPSEEK_API_KEY=sk-...`；云端请在 Advanced settings → Secrets 里配置。"
                )
                    st.session_state["result"] = {
                        "text": text.strip(),
                        "hits": hits,
                        "advice": None,
                        "rewritten": False,
                    }
                else:
                    with st.spinner("正在调用 DeepSeek 改写……"):
                        try:
                            advice = core.rewrite_with_deepseek(text, hits, api_key=key)
                            st.session_state["result"] = {
                                "text": text.strip(),
                                "hits": hits,
                                "advice": advice,
                                "rewritten": True,
                            }
                        except Exception as exc:  # noqa: BLE001 - 界面统一兜底
                            st.session_state["result"] = {
                                "text": text.strip(),
                                "hits": hits,
                                "advice": None,
                                "rewritten": False,
                            }
                            msg = str(exc)
                            if "401" in msg or "Authentication" in msg:
                                st.error(f"改写失败：API Key 无效或已删除。\n\n`{msg}`")
                            else:
                                st.error(f"改写失败：{msg}")

    with right:
        result = st.session_state.get("result")
        if result is None:
            st.info(
                "**怎么用**\n\n"
                "1. 左边粘贴口播稿\n"
                "2. 点「开始校验」\n"
                "3. 看命中列表，按依据判断\n\n"
                "命中 0 条时不会调用模型，不产生费用。"
            )
            st.divider()
            st.caption("规则库未覆盖的语义层风险（暗示疗效、贬低同行、虚构产地等）仍需人工确认。")
        else:
            hits = result["hits"]
            m1, m2, m3 = st.columns(3)
            m1.metric("命中条数", len(hits))
            m2.metric("最高风险", top_risk(hits))
            m3.metric("规则总数", len(rules))

            if not hits:
                st.success("未命中硬规则 ✅")
                st.caption("规则库未覆盖的语义层风险仍需人工确认。")
            else:
                st.markdown("**原稿命中位置**")
                st.markdown(
                    '<div style="white-space:pre-wrap;line-height:2;background:#fafafa;'
                    'border:1px solid #eee;border-radius:8px;padding:12px;font-size:15px;">'
                    f"{highlight(result['text'], hits)}</div>",
                    unsafe_allow_html=True,
                )
                st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

                for h in hits:
                    with st.expander(
                        f"{RISK_BADGE.get(h['risk'], '⚪')} {h['rule_id']} · {h['risk']} · "
                        f"命中「{h['matched']}」",
                        expanded=len(hits) <= 2,
                    ):
                        st.markdown(h["reason"])
                        st.caption(f"依据：{h['source']}")
                        st.caption(f"上下文：…{h['context']}…")

    # 改写结果放整行，方便复制
    result = st.session_state.get("result")
    if result and result["hits"]:
        st.divider()
        if result["rewritten"] and result["advice"]:
            notes, rewritten = split_advice(result["advice"])
            st.subheader("DeepSeek 改写建议")
            c1, c2 = st.columns([3, 2], gap="large")
            with c1:
                st.markdown("**逐条说明**")
                st.markdown(notes or "（模型未给出说明）")
            with c2:
                st.markdown("**改写文案（可编辑后复制）**")
                edited = st.text_area(
                    "改写文案",
                    value=rewritten,
                    height=320,
                    key="edited_copy",
                    label_visibility="collapsed",
                )
                st.download_button(
                    "下载改写稿",
                    data=edited or rewritten,
                    file_name="改写文案.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            st.info("AI 辅助建议，规则出处已标注，最终发布前请人工确认。")
        elif not result["rewritten"]:
            st.caption("已跳过模型改写：仅展示规则体检结果。")

# ---------- 批量体检 ----------
with tab_batch:
    st.markdown("一行一条口播稿，只跑规则、不调模型 —— 适合先把整场脚本筛一遍。")
    batch = st.text_area(
        "批量文案",
        height=220,
        placeholder="家人们看这棵桂花，四季开花，养死包赔……\n不拍保温棉，冻坏不赔啊\n这款月季含7天绿植险，秋季盛花",
        key="batch_text",
        label_visibility="collapsed",
    )
    if st.button("批量体检", type="primary", key="batch_run"):
        lines = [ln.strip() for ln in batch.splitlines() if ln.strip()]
        if not lines:
            st.warning("请先粘贴文案，一行一条。")
        else:
            rows = []
            for idx, line in enumerate(lines, 1):
                hits = core.lint(line, rules)
                rows.append(
                    {
                        "序号": idx,
                        "文案": line,
                        "命中数": len(hits),
                        "最高风险": top_risk(hits),
                        "命中规则": "、".join(f"{h['rule_id']}({h['matched']})" for h in hits) or "—",
                    }
                )
            risky = sum(1 for r in rows if r["命中数"])
            st.success(f"共 {len(rows)} 条，{risky} 条命中硬规则。")
            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "序号": st.column_config.NumberColumn(width="small"),
                    "文案": st.column_config.TextColumn(width="large"),
                    "命中数": st.column_config.NumberColumn(width="small"),
                },
            )

# ---------- 规则库 ----------
with tab_rules:
    st.caption("改规则请直接编辑 rules.json / replacements.json，刷新页面即生效。")
    for r in rules:
        with st.expander(f"{RISK_BADGE.get(r['risk'], '⚪')} {r['id']} · {r['risk']} · `{r['regex'].pattern}`"):
            st.markdown(r["reason"])
            st.caption(f"依据：{r['source']}")
    st.divider()
    st.markdown("**替换表分组**")
    st.write("、".join(f"`{k}`（{len(v)} 条）" for k, v in replacements.items()))
