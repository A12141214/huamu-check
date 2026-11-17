"""app.py —— 花木口播文案合规校验（Streamlit 网页版 · 多条批量）。

界面层只负责展示；规则匹配、替换分组、模型改写全部复用 check.py，
避免两份逻辑各改各的、线上和本地结果不一致。

本地运行：
    streamlit run app.py
"""

from __future__ import annotations

import html
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check as core  # noqa: E402  - 复用检测/改写逻辑，这里不重复实现

st.set_page_config(
    page_title="花木口播文案合规校验",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

RISK_BADGE = {"极高": "🔴", "高": "🟠", "中": "🟡", "低": "🟢"}
RISK_CLASS = {"极高": "hm-risk-a", "高": "hm-risk-b", "中": "hm-risk-c", "低": "hm-risk-d"}
MAX_PARALLEL = 4

# ---------- 样式 ----------
st.markdown(
    """
<style>
  :root{
    --hm-ink:#16211a; --hm-muted:#68756b; --hm-green:#1f7a3f; --hm-green-l:#2f9e56;
    --hm-line:#e3e9e4; --hm-card:#ffffff; --hm-bg:#f6f8f6;
  }
  .block-container{padding-top:1.6rem; padding-bottom:3rem; max-width:1240px;}
  #MainMenu, footer{visibility:hidden;}

  .hm-hero{
    background:linear-gradient(135deg,#123d24 0%,#1f7a3f 55%,#2f9e56 100%);
    border-radius:20px; padding:26px 30px; color:#fff; position:relative; overflow:hidden;
    box-shadow:0 12px 30px -12px rgba(18,61,36,.55);
  }
  .hm-hero:after{
    content:""; position:absolute; right:-40px; top:-60px; width:240px; height:240px;
    background:radial-gradient(circle,rgba(255,255,255,.18),transparent 65%); border-radius:50%;
  }
  .hm-hero h1{margin:0 0 6px; font-size:27px; font-weight:700; letter-spacing:.3px; color:#fff;}
  .hm-hero p{margin:0; color:#d8ecdd; font-size:14px;}
  .hm-chips{margin-top:14px; display:flex; gap:8px; flex-wrap:wrap;}
  .hm-chip{
    display:inline-block; padding:4px 11px; border-radius:999px; font-size:12.5px;
    background:rgba(255,255,255,.14); color:#eaf6ec; border:1px solid rgba(255,255,255,.18);
  }

  .hm-card{
    background:var(--hm-card); border:1px solid var(--hm-line); border-radius:16px;
    padding:18px 20px; box-shadow:0 1px 2px rgba(16,24,18,.04);
  }
  .hm-item-head{display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:10px;}
  .hm-idx{
    width:26px; height:26px; border-radius:8px; background:#eef4ef; color:#2a5b3c;
    display:inline-flex; align-items:center; justify-content:center; font-size:13px; font-weight:700;
  }
  .hm-risk{font-size:12px; padding:2px 9px; border-radius:999px; font-weight:600;}
  .hm-risk-a{background:#fdeaea; color:#a31616;}
  .hm-risk-b{background:#fdf0e3; color:#9a4b06;}
  .hm-risk-c{background:#fdf6dd; color:#7d5c05;}
  .hm-risk-d{background:#e9f5ec; color:#1f6b39;}
  .hm-tag{
    font-size:12px; padding:2px 9px; border-radius:999px; background:#f1f4f2;
    color:#4a5a4f; border:1px solid #e6ebe7;
  }
  .hm-orig{
    white-space:pre-wrap; line-height:1.95; font-size:15px;
    background:#fbfcfb; border:1px solid #eef2ee; border-radius:12px; padding:13px 15px;
  }
  mark{background:#ffe0e0; color:#9c1010; padding:0 3px; border-radius:4px; font-weight:600;}

  .hm-sug-block{
    margin-top:10px; background:#f2f9f3; border:1px solid #d9ecdd; border-left:3px solid #2f9e56;
    border-radius:10px; padding:11px 14px; font-size:14px; line-height:1.9;
  }
  .hm-sug-title{font-size:12.5px; color:#3d6b4a; font-weight:700; margin-bottom:4px; letter-spacing:.5px;}
  .hm-sug-row{color:#2c3d31;}
  .hm-sug-row .from{color:#a31616; text-decoration:line-through; text-decoration-thickness:1px;}
  .hm-sug-row .to{color:#1f6b39; font-weight:600;}

  div[data-testid="stMetric"]{
    background:var(--hm-card); border:1px solid var(--hm-line); border-radius:14px;
    padding:14px 16px; box-shadow:0 1px 2px rgba(16,24,18,.04);
  }
  div[data-testid="stMetricValue"]{font-size:26px; font-weight:700; color:var(--hm-ink);}
  div[data-testid="stMetricLabel"]{color:var(--hm-muted);}

  .stButton>button{
    border-radius:10px; border:1px solid var(--hm-line); font-weight:600;
    transition:all .15s ease;
  }
  .stButton>button[kind="primary"]{
    background:linear-gradient(135deg,#1f7a3f,#2f9e56); border:none;
    box-shadow:0 6px 16px -8px rgba(31,122,63,.7);
  }
  .stButton>button[kind="primary"]:hover{transform:translateY(-1px); box-shadow:0 10px 20px -8px rgba(31,122,63,.8);}

  .stTextArea textarea{border-radius:12px; border-color:var(--hm-line); font-size:15px; line-height:1.8;}
  .stTextArea textarea:focus{box-shadow:0 0 0 3px rgba(47,158,86,.16); border-color:#7cc194;}

  div[data-testid="stExpander"]{border-radius:12px; border-color:var(--hm-line);}
  div[data-testid="stExpander"] summary{font-size:14px;}
  /* 改写稿是整段口播，长句要换行，不要横向截断 */
  div[data-testid="stCode"]{border-radius:12px; max-width:100%;}
  div[data-testid="stCode"] pre{
    white-space:pre-wrap !important; word-break:break-word; overflow-x:hidden;
    line-height:1.95; font-size:14.5px; padding-right:6px;
  }
  .stTabs [data-baseweb="tab-list"]{gap:6px;}
  .stTabs [data-baseweb="tab"]{border-radius:9px 9px 0 0; padding:8px 16px; font-weight:600;}
</style>
""",
    unsafe_allow_html=True,
)


# ========== 资源与配置 ==========
def load_rules() -> list[dict]:
    return core.load_rules()


def load_replacements() -> dict:
    return core.load_replacements()


def get_api_key() -> str | None:
    """优先级：侧栏临时填写 > Streamlit Secrets > 环境变量 / .env。"""
    tmp = (st.session_state.get("tmp_key") or "").strip()
    if tmp:
        return tmp
    try:
        if "DEEPSEEK_API_KEY" in st.secrets:  # type: ignore[attr-defined]
            key = str(st.secrets["DEEPSEEK_API_KEY"]).strip()  # type: ignore[attr-defined]
            if key:
                return key
    except Exception:
        pass
    core._load_dotenv()
    return (os.getenv("DEEPSEEK_API_KEY") or "").strip() or None


# ========== 展示辅助 ==========
def merge_spans(hits: list[dict]) -> list[tuple[int, int]]:
    spans = sorted((h["start"], h["end"]) for h in hits)
    merged: list[list[int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(s, e) for s, e in merged]


def highlight(text: str, hits: list[dict]) -> str:
    parts: list[str] = []
    cursor = 0
    for start, end in merge_spans(hits):
        parts.append(html.escape(text[cursor:start]))
        parts.append(f"<mark>{html.escape(text[start:end])}</mark>")
        cursor = end
    parts.append(html.escape(text[cursor:]))
    return "".join(parts)


def split_advice(advice: str) -> tuple[str, str]:
    if "【改写文案】" not in advice:
        return advice.strip(), ""
    head, tail = advice.split("【改写文案】", 1)
    return head.replace("【逐条说明】", "").strip(), tail.strip()


def top_risk(hits: list[dict]) -> str:
    return hits[0]["risk"] if hits else "无"


# ========== 页面 ==========
rules = load_rules()
replacements = load_replacements()
categories = core.load_categories()
platforms = core.load_platforms()
auto_rules = [r for r in rules if not r["manual_review"]]
universal = [r for r in auto_rules if "all" in r["platform"]]
platform_only = [r for r in auto_rules if "all" not in r["platform"]]

st.markdown(
    f"""
<div class="hm-hero">
  <h1>🌿 花木文案合规校验</h1>
  <p>淘宝 / 拼多多 / 京东三平台 —— 通用底座 + 平台差异层，一行一条粘贴整场脚本</p>
  <div class="hm-chips">
    <span class="hm-chip">{len(universal)} 条通用规则</span>
    <span class="hm-chip">{len(platform_only)} 条平台专属</span>
    <span class="hm-chip">{len(categories)} 个类别</span>
    <span class="hm-chip">未命中不调用模型 · 不计费</span>
  </div>
</div>
""",
    unsafe_allow_html=True,
)

# 平台选择：all = 通用底座，其余叠加该平台的差异层规则
_pname_to_code = {v: k for k, v in platforms.items()}
_choice = st.segmented_control(
    "校验平台",
    list(platforms.values()),
    default=platforms.get("all", "三平台通用"),
    label_visibility="collapsed",
    key="platform_choice",
)
platform = _pname_to_code.get(_choice or "", "all")
manual_items = core.manual_review_items(rules, categories, platform)
active_rules = [r for r in auto_rules if core.rule_applies(r, platform)]

with st.sidebar:
    st.markdown("#### 配置自检")
    try:
        secret_names = list(st.secrets.keys())  # type: ignore[attr-defined]
    except Exception:
        secret_names = []
    key_ready = bool(get_api_key())
    st.markdown(
        f"""<div class="hm-card" style="padding:14px 16px">
        <div style="font-size:13px;color:#68756b">Secrets 键</div>
        <div style="font-size:14px;font-weight:600;margin-bottom:10px">
          {'、'.join(secret_names) if secret_names else '（未读到）'}</div>
        <div style="font-size:13px;color:#68756b">API Key</div>
        <div style="font-size:14px;font-weight:600">{'✅ 已就绪' if key_ready else '❌ 未配置'}</div>
        </div>""",
        unsafe_allow_html=True,
    )
    if not key_ready:
        st.text_input(
            "临时 API Key（会话级）",
            type="password",
            key="tmp_key",
            placeholder="sk-...",
            help="只对当前浏览器会话有效，不落盘、不进仓库。长期使用请配 Settings → Secrets。",
        )
    st.divider()
    st.caption("云端配置：应用页 `⋮` → `Settings` → `Secrets`")
    st.caption('内容：`DEEPSEEK_API_KEY = "sk-..."`')

SAMPLE = """家人们看这棵桂花，四季开花，养死包赔，全网最低价，喜欢的赶紧下单！
这款月季包开花，招财辟邪，还能降血压，30天发芽！
南北方均可种植，浇水就活，新手也能养，所见即所得
这款月季含7天绿植险，秋季盛花，具体以详情页为准"""


def _fill_sample() -> None:
    st.session_state["bulk_text"] = SAMPLE
    st.session_state.pop("bulk_result", None)


tab_check, tab_rules = st.tabs(["文案校验", "规则库"])

# ---------- 文案校验 ----------
with tab_check:
    raw = st.text_area(
        "口播文案（一行一条）",
        height=210,
        placeholder=SAMPLE,
        key="bulk_text",
        label_visibility="collapsed",
    )

    c1, c2, c3, c4 = st.columns([2, 1.2, 1.6, 2.2])
    run = c1.button("开始校验", type="primary", use_container_width=True)
    c2.button("填入示例", use_container_width=True, on_click=_fill_sample)
    rule_only = c3.checkbox("只做规则体检（不调模型）", value=False)
    max_rewrite = c4.slider(
        "最多改写条数（控制费用）", 1, 20, 6,
        help="命中违规的文案会各调用一次模型。超出的只做体检，不产生费用。",
    )

    if run:
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if not lines:
            st.warning("请先粘贴文案，一行一条。")
            st.session_state.pop("bulk_result", None)
        else:
            key = get_api_key()
            items = []
            for idx, line in enumerate(lines, 1):
                hits = core.lint(line, rules, replacements, platform)
                items.append(
                    {"idx": idx, "text": line, "hits": hits, "advice": None, "rewritten": False, "error": None}
                )

            todo = [it for it in items if it["hits"]] if not rule_only else []
            if rule_only:
                st.session_state["bulk_result"] = {
                    "items": items,
                    "rule_only": True,
                    "skipped_rewrite": len([i for i in items if i["hits"]]),
                    "key_missing": False,
                }
            elif not todo:
                st.session_state["bulk_result"] = {
                    "items": items, "rule_only": False, "skipped_rewrite": 0, "key_missing": False
                }
            elif not key:
                st.session_state["bulk_result"] = {
                    "items": items, "rule_only": False, "skipped_rewrite": len(todo), "key_missing": True
                }
            else:
                batch = todo[:max_rewrite]
                skipped = len(todo) - len(batch)
                progress = st.progress(0.0, text=f"正在并行改写 0/{len(batch)} 条…")

                def _work(item: dict) -> str:
                    return core.rewrite_with_deepseek(
                        item["text"], item["hits"], api_key=key, replacements=replacements
                    )

                done = 0
                with ThreadPoolExecutor(max_workers=MAX_PARALLEL) as pool:
                    futures = {pool.submit(_work, it): it for it in batch}
                    for fut in as_completed(futures):
                        item = futures[fut]
                        try:
                            item["advice"] = fut.result()
                            item["rewritten"] = True
                        except Exception as exc:  # noqa: BLE001
                            item["error"] = str(exc)
                        done += 1
                        progress.progress(done / len(batch), text=f"正在并行改写 {done}/{len(batch)} 条…")
                progress.empty()

                st.session_state["bulk_result"] = {
                    "items": items,
                    "rule_only": False,
                    "skipped_rewrite": skipped,
                    "key_missing": False,
                }

    result = st.session_state.get("bulk_result")

    if result:
        items = result["items"]
        total_hits = sum(len(i["hits"]) for i in items)
        risky = [i for i in items if i["hits"]]
        rewritten = [i for i in items if i["rewritten"]]

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("文案条数", len(items))
        m2.metric("命中条数", total_hits)
        m3.metric("需处理", len(risky))
        _order = {"极高": 0, "高": 1, "中": 2, "低": 3, "无": 4}
        worst = min((top_risk(i["hits"]) for i in items), key=lambda r: _order.get(r, 9), default="无")
        m4.metric("最高风险", worst)

        if result["key_missing"]:
            st.error(
                "未配置 DEEPSEEK_API_KEY：右侧栏可临时填写，或在 Settings → Secrets 配置。"
                "当前仅完成规则体检。"
            )
        elif result["rule_only"]:
            st.caption(f"只做规则体检，跳过 {result['skipped_rewrite']} 条命中文案的模型改写。")
        if result.get("skipped_rewrite") and not result["key_missing"] and not result["rule_only"]:
            st.warning(f"有 {result['skipped_rewrite']} 条超出改写上限，只做了体检。调高滑块可继续。")

        if not risky:
            st.success("全部文案未命中硬规则 ✅ — 语义层风险仍需人工确认。")
        else:
            if rewritten:
                bundle = "\n\n".join(
                    f"#{i['idx']} 原文：{i['text']}\n改写：{split_advice(i['advice'])[1]}"
                    for i in rewritten
                )
                st.download_button(
                    "下载全部改写稿",
                    data=bundle,
                    file_name="改写文案.txt",
                    mime="text/plain",
                )

            st.markdown("### 逐条结果")
            for item in items:
                hits = item["hits"]
                if not hits:
                    with st.container(border=True):
                        st.markdown(
                            f'<div class="hm-item-head"><span class="hm-idx">{item["idx"]}</span>'
                            f'<span class="hm-tag">未命中</span></div>'
                            f'<div class="hm-orig">{html.escape(item["text"])}</div>',
                            unsafe_allow_html=True,
                        )
                    continue

                risk = top_risk(hits)
                cats = sorted({h.get("category", "") for h in hits if h.get("category")})
                cat_txt = " · ".join(f"{c} {categories.get(c, '')}" for c in cats)
                with st.container(border=True):
                    st.markdown(
                        f'<div class="hm-item-head">'
                        f'<span class="hm-idx">{item["idx"]}</span>'
                        f'<span class="hm-risk {RISK_CLASS.get(risk, "hm-risk-d")}">{RISK_BADGE.get(risk, "")} {risk}</span>'
                        f'<span class="hm-tag">{len(hits)} 处命中</span>'
                        f'<span class="hm-tag">{html.escape(cat_txt)}</span>'
                        + (
                            '<span class="hm-tag" style="background:#e8f5ec;color:#1f6b39;border-color:#cfe8d8">已改写</span>'
                            if item["rewritten"]
                            else ""
                        )
                        + f'</div><div class="hm-orig">{highlight(item["text"], hits)}</div>',
                        unsafe_allow_html=True,
                    )

                    # 推荐修改文案：按替换表直接给，不依赖模型，秒出
                    sugg = [(h["matched"], h["suggestion"]) for h in hits if h.get("suggestion")]
                    if sugg:
                        rows = "".join(
                            f'<div class="hm-sug-row">{html.escape(src)} → '
                            f'<span class="to">{html.escape(dst)}</span></div>'
                            for src, dst in sugg
                        )
                        st.markdown(
                            f'<div class="hm-sug-block"><div class="hm-sug-title">推荐修改文案</div>{rows}</div>',
                            unsafe_allow_html=True,
                        )

                    with st.expander("查看命中明细与依据"):
                        for h in hits:
                            cat = categories.get(h.get("category", ""), "")
                            st.markdown(
                                f"**{h['rule_id']}** · {h['category']} {cat} · {h['risk']} · "
                                f"命中「{h['matched']}」"
                            )
                            st.markdown(h["reason"])
                            if h.get("suggestion"):
                                st.success(f"建议改为：{h['suggestion']}")
                            st.caption(f"依据：{h['source']}")
                            st.divider()

                    if item["rewritten"] and item["advice"]:
                        notes, rewritten_text = split_advice(item["advice"])
                        st.markdown("**合规改写**")
                        st.code(rewritten_text or "（模型未给出改写文案）", language=None, wrap_lines=True)
                        if notes:
                            with st.expander("查看逐条说明"):
                                st.markdown(notes)
                    elif item["error"]:
                        st.error(f"改写失败：{item['error'][:200]}")
                    else:
                        st.caption("未改写（超出上限或只做体检）")

        if manual_items:
            with st.expander(f"⚠️ 另有 {len(manual_items)} 条需人工复核（不计入命中数）"):
                st.caption(
                    "这些规则依赖“口播 vs 详情页”的跨源比对，正则判不了。"
                    "即使显示 0 命中，也不代表完全合规。"
                )
                for m in manual_items:
                    st.markdown(f"**{m['rule_id']}** · {m['category']} {m['category_name']} · {m['risk']}")
                    st.caption(m["reason"])
                    st.caption(f"依据：{m['source']}")

# ---------- 规则库 ----------
with tab_rules:
    st.caption(
        f"当前平台：**{platforms.get(platform, platform)}** —— 共 {len(active_rules)} 条规则生效"
        f"（通用底座 {len(universal)} 条 + 平台专属 {len([r for r in active_rules if 'all' not in r['platform']])} 条）。"
        "改规则直接编辑 rules.json / replacements.json，刷新页面即生效。"
    )
    for code, name in categories.items():
        group = [r for r in rules if r["category"] == code and core.rule_applies(r, platform)]
        if not group:
            continue
        st.markdown(f"#### {code} · {name}（{len(group)} 条）")
        for r in group:
            if r["manual_review"]:
                tag = "需人工复核"
            else:
                tag = f"`{r['regex'].pattern}`"
            scope = "通用" if "all" in r["platform"] else platforms.get(r["platform"][0], "")
            scope_tag = "" if scope == "通用" else f" · 🔖{scope}"
            with st.expander(
                f"{RISK_BADGE.get(r['risk'], '⚪')} {r['id']}{scope_tag} · {r['risk']} · {tag}"
            ):
                st.markdown(r["reason"])
                st.caption(f"依据：{r['source']}")

    st.divider()
    st.markdown("**替换表分组**")
    st.write("、".join(f"`{k}`（{len(v)} 条）" for k, v in replacements.items() if isinstance(v, dict)))
