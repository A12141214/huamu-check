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
    --ink:#0E1A12; --ink-2:#26332A; --muted:#68766C; --muted-2:#8A978E;
    --green:#1B7A43; --green-d:#0D4225; --green-l:#37A868; --green-x:#67CE93;
    --line:#E4EBE6; --line-2:#EEF4EF;
    --grad-brand:linear-gradient(135deg,#0B3A1F 0%,#12522F 42%,#1E8348 74%,#3AAE6A 100%);
    --grad-text:linear-gradient(96deg,#0D4225 0%,#1B7A43 52%,#3AAE6A 100%);
    --grad-soft:linear-gradient(180deg,#FFFFFF 0%,#F7FBF8 100%);
    --grad-line:linear-gradient(90deg,rgba(27,122,67,.5),rgba(27,122,67,0));
  }
  html, body, [class*="css"]{
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;
    -webkit-font-smoothing:antialiased;
  }
  /* 页面底：极浅的绿白渐变 + 顶部一层柔光，避免整页死白 */
  .stApp{
    background:
      radial-gradient(1100px 420px at 8% -6%, rgba(58,174,106,.10), transparent 62%),
      radial-gradient(900px 380px at 96% 4%, rgba(27,122,67,.07), transparent 58%),
      linear-gradient(180deg,#F4FAF6 0%,#FBFDFB 38%,#F6FAF7 100%);
    background-attachment:fixed;
  }
  .block-container{padding-top:1.4rem; padding-bottom:4rem; max-width:1180px;}
  #MainMenu, footer{visibility:hidden;}

  /* ---------- Hero ---------- */
  .hm-hero{
    position:relative; overflow:hidden; border-radius:22px;
    padding:30px 34px 26px; color:#fff;
    background:
      radial-gradient(900px 260px at 14% -20%, rgba(120,222,160,.55), transparent 62%),
      radial-gradient(760px 300px at 88% 130%, rgba(16,94,55,.75), transparent 64%),
      var(--grad-brand);
    box-shadow:0 20px 44px -24px rgba(11,58,31,.8), inset 0 1px 0 rgba(255,255,255,.10);
  }
  .hm-hero:before{
    content:""; position:absolute; inset:0; opacity:.14;
    background-image:radial-gradient(rgba(255,255,255,.6) 1px, transparent 1px);
    background-size:18px 18px; mask-image:linear-gradient(120deg,#000,transparent 70%);
  }
  .hm-hero:after{
    content:""; position:absolute; right:-90px; top:-120px; width:340px; height:340px; border-radius:50%;
    background:radial-gradient(circle,rgba(103,206,147,.35),transparent 62%);
    filter:blur(6px);
  }
  .hm-hero-in{position:relative; z-index:1}
  .hm-eyebrow{
    display:inline-flex; align-items:center; gap:7px; font-size:11.5px; letter-spacing:1.5px;
    text-transform:uppercase; font-weight:700; margin-bottom:11px;
    background:linear-gradient(90deg,#CFF3DC,#8FE3B2);
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .hm-eyebrow i{
    width:6px; height:6px; border-radius:50%; background:#6DE39A; display:inline-block;
    box-shadow:0 0 0 4px rgba(109,227,154,.16), 0 0 12px rgba(109,227,154,.8);
  }
  .hm-hero h1{
    margin:0; font-size:29px; line-height:1.25; font-weight:700; letter-spacing:.4px;
    background:linear-gradient(180deg,#FFFFFF 30%,#C9EBD6 100%);
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .hm-hero p{margin:9px 0 0; color:rgba(224,242,231,.82); font-size:13.5px; letter-spacing:.2px;}
  .hm-chips{margin-top:18px; display:flex; gap:8px; flex-wrap:wrap;}
  .hm-chip{
    display:inline-flex; align-items:center; gap:6px; padding:5px 12px; border-radius:999px;
    font-size:12px; letter-spacing:.3px; color:#EAF8EF;
    background:linear-gradient(135deg,rgba(255,255,255,.18),rgba(255,255,255,.07));
    border:1px solid rgba(255,255,255,.20);
    box-shadow:inset 0 1px 0 rgba(255,255,255,.14);
    backdrop-filter:blur(6px);
  }
  .hm-chip b{
    font-weight:700; font-variant-numeric:tabular-nums;
    background:linear-gradient(180deg,#FFFFFF,#BFF0D1);
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }

  /* ---------- 平台切换 ---------- */
  .hm-plat{margin:22px 0 6px; display:flex; align-items:center; gap:12px;}
  .hm-plat .lb{
    font-size:11.5px; letter-spacing:1.2px; font-weight:700; text-transform:uppercase;
    background:var(--grad-text); -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .hm-plat .line{flex:1; height:1px; background:var(--grad-line);}
  div[data-testid="stButtonGroup"] button, div[data-testid="stSegmentedControl"] button{
    border-radius:9px !important; font-size:13px !important; font-weight:600 !important;
    padding:6px 16px !important; border:1px solid var(--line) !important;
    background:linear-gradient(180deg,#FFFFFF,#F6FAF7) !important;
    transition:all .18s ease;
  }
  div[data-testid="stButtonGroup"] button:hover, div[data-testid="stSegmentedControl"] button:hover{
    border-color:#B9DCC6 !important; color:var(--green-d) !important;
  }
  div[data-testid="stButtonGroup"] button[aria-checked="true"],
  div[data-testid="stSegmentedControl"] button[aria-checked="true"]{
    background:linear-gradient(135deg,#EAF7EF,#D6F0E0) !important;
    color:var(--green-d) !important; border-color:#A9DCC0 !important;
    box-shadow:inset 0 1px 0 #fff, 0 2px 8px -4px rgba(27,122,67,.5) !important;
  }

  /* ---------- 区块标题 ---------- */
  .hm-section{display:flex; align-items:baseline; gap:10px; margin:26px 0 12px;}
  .hm-section h2{
    margin:0; font-size:17px; font-weight:700; letter-spacing:.3px;
    background:var(--grad-text); -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .hm-section .cnt{
    font-size:11.5px; color:#1F6B3F; font-variant-numeric:tabular-nums;
    background:linear-gradient(135deg,#EAF7EF,#F7FCF9); border:1px solid #CBEBDA;
    border-radius:999px; padding:2px 10px;
  }
  .hm-section .hint{margin-left:auto; font-size:12px; color:var(--muted-2);}

  /* ---------- 指标卡 ---------- */
  div[data-testid="stMetric"]{
    position:relative; overflow:hidden;
    background:linear-gradient(180deg,#FFFFFF 0%,#F5FBF7 100%);
    border:1px solid #E1EDE5; border-radius:14px; padding:16px 18px 14px;
    box-shadow:0 1px 2px rgba(15,26,19,.04), inset 0 1px 0 #fff;
    transition:box-shadow .2s ease, transform .2s ease;
  }
  div[data-testid="stMetric"]:before{
    content:""; position:absolute; left:0; right:0; top:0; height:3px;
    background:linear-gradient(90deg,#1B7A43,#3AAE6A 45%,#67CE93 80%,rgba(103,206,147,0));
  }
  div[data-testid="stMetric"]:hover{transform:translateY(-2px); box-shadow:0 14px 26px -20px rgba(15,26,19,.6);}
  div[data-testid="stMetricLabel"] p{
    font-size:11.5px !important; letter-spacing:.6px; color:var(--muted) !important; font-weight:600;
  }
  div[data-testid="stMetricValue"]{
    font-size:27px !important; font-weight:700 !important; font-variant-numeric:tabular-nums;
    background:linear-gradient(135deg,#0E2A19,#1B7A43 70%);
    -webkit-background-clip:text; background-clip:text; color:transparent !important;
  }

  /* ---------- 结果卡 ---------- */
  div[data-testid="stVerticalBlockBorderWrapper"]{
    border-radius:14px !important; border:1px solid var(--line) !important;
    background:linear-gradient(180deg,#FFFFFF 0%,#FAFCFA 100%);
    box-shadow:0 1px 2px rgba(15,26,19,.04), inset 0 1px 0 #fff;
    transition:box-shadow .2s ease, border-color .2s ease, transform .2s ease;
  }
  div[data-testid="stVerticalBlockBorderWrapper"]:hover{
    transform:translateY(-1px);
    box-shadow:0 18px 34px -28px rgba(15,26,19,.7); border-color:#D3E7DA !important;
  }
  .hm-head{display:flex; align-items:center; gap:9px; flex-wrap:wrap; margin-bottom:12px;}
  .hm-idx{
    font:600 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;
    color:#2F6B47; background:linear-gradient(180deg,#F2F8F4,#E9F3ED);
    border:1px solid #DCEAE0; border-radius:7px; padding:4px 8px; font-variant-numeric:tabular-nums;
  }
  .hm-risk{
    font-size:11.5px; font-weight:700; letter-spacing:.4px; padding:3px 11px; border-radius:999px;
    border:1px solid transparent; box-shadow:inset 0 1px 0 rgba(255,255,255,.7);
  }
  .hm-risk-a{color:#9E1B10; background:linear-gradient(135deg,#FDECEA,#F9D3CD); border-color:#F2C4BC;}
  .hm-risk-b{color:#9A4708; background:linear-gradient(135deg,#FFF6E8,#FCE4C2); border-color:#F3D6A8;}
  .hm-risk-c{color:#7A5803; background:linear-gradient(135deg,#FFFBEB,#F8EDC4); border-color:#EDDFA9;}
  .hm-risk-d{color:#166B3C; background:linear-gradient(135deg,#EAF7EF,#D8F0E1); border-color:#BEE3CD;}
  .hm-tag{
    font-size:11.5px; letter-spacing:.2px; padding:3px 9px; border-radius:6px;
    background:linear-gradient(180deg,#F7FAF8,#F1F6F3); color:#58685E; border:1px solid #E3EDE7;
  }
  .hm-tag.ok{background:linear-gradient(135deg,#EAF8EF,#DCF2E4); color:#14663A; border-color:#BFE4CE;}
  .hm-tag.cat{background:linear-gradient(180deg,#FAFCFA,#F4F8F5); color:#5E6E63;}

  .hm-orig{
    white-space:pre-wrap; line-height:2; font-size:14.8px; color:var(--ink-2);
    background:linear-gradient(180deg,#FCFDFC,#F8FBF9);
    border:1px solid var(--line-2); border-radius:10px; padding:13px 15px;
  }
  mark{
    background:linear-gradient(180deg,transparent 56%,#FFD3CD 56%,#FFC9C2 100%);
    color:#8C1509; font-weight:600; padding:0 2px; border-radius:2px;
  }

  /* ---------- 推荐修改 ---------- */
  .hm-sug{
    margin-top:12px; border:1px solid #D8EBDF; border-radius:12px; overflow:hidden;
    box-shadow:0 1px 2px rgba(15,26,19,.03);
  }
  .hm-sug-head{
    display:flex; align-items:center; gap:7px; padding:9px 14px;
    background:linear-gradient(90deg,#EAF7EF,#F4FBF7 60%,#FFFFFF);
    border-bottom:1px solid #E1F0E7;
    font-size:11.5px; font-weight:700; letter-spacing:1.1px; text-transform:uppercase;
    background-clip:padding-box;
  }
  .hm-sug-head span{
    background:linear-gradient(90deg,#16663C,#2E9A57);
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .hm-sug-body{background:linear-gradient(180deg,#FFFFFF,#FBFDFB); padding:6px 14px 10px;}
  .hm-sug-row{
    display:flex; gap:10px; align-items:flex-start; padding:7px 0; font-size:13.8px; line-height:1.75;
    border-bottom:1px dashed #E9F1EB;
  }
  .hm-sug-row:last-child{border-bottom:none;}
  .hm-sug-row .from{
    flex:0 0 auto; color:#96271A; background:linear-gradient(135deg,#FDEFED,#FBE2DD);
    border:1px solid #F4D2CB; border-radius:5px; padding:1px 8px; font-size:12.5px;
    text-decoration:line-through; text-decoration-thickness:.5px; text-decoration-color:#CA7768;
    white-space:nowrap;
  }
  .hm-sug-row .arrow{color:#A9BBB0; flex:0 0 auto;}
  .hm-sug-row .to{color:#1E5437; font-weight:500;}

  /* ---------- 空状态 ---------- */
  .hm-empty{
    margin-top:22px; border:1px dashed #CFE3D7; border-radius:18px; padding:30px 28px; text-align:center;
    background:
      radial-gradient(600px 200px at 50% -20%, rgba(58,174,106,.10), transparent 70%),
      linear-gradient(180deg,#FCFEFD,#F6FAF8);
  }
  .hm-empty h3{
    margin:0 0 6px; font-size:16px; font-weight:700;
    background:var(--grad-text); -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .hm-empty p{margin:0 0 18px; color:var(--muted); font-size:13.5px;}
  .hm-steps{display:flex; gap:12px; justify-content:center; flex-wrap:wrap;}
  .hm-step{
    background:linear-gradient(180deg,#FFFFFF,#F7FBF8); border:1px solid var(--line);
    border-radius:12px; padding:12px 16px; min-width:190px; text-align:left;
    box-shadow:0 1px 2px rgba(15,26,19,.03), inset 0 1px 0 #fff;
  }
  .hm-step b{
    display:block; font-size:10.5px; letter-spacing:1.2px; margin-bottom:5px;
    background:linear-gradient(90deg,#1B7A43,#4FBB7B);
    -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .hm-step span{font-size:13px; color:var(--ink-2); line-height:1.6;}

  /* ---------- 控件 ---------- */
  .stButton>button{
    border-radius:10px; border:1px solid var(--line); font-weight:600; font-size:13.5px;
    background:linear-gradient(180deg,#FFFFFF,#F5FAF7); transition:all .18s ease; padding:.5rem 1rem;
  }
  .stButton>button:hover{
    border-color:#A9DCC0; color:var(--green-d); transform:translateY(-1px);
    box-shadow:0 10px 20px -18px rgba(15,26,19,.8);
  }
  .stButton>button[kind="primary"]{
    background:linear-gradient(135deg,#0E4A28 0%,#1B7A43 46%,#39AC69 100%);
    background-size:180% 180%; background-position:0% 50%;
    border:1px solid rgba(0,0,0,.08); color:#fff;
    box-shadow:0 10px 22px -14px rgba(21,110,60,.95), inset 0 1px 0 rgba(255,255,255,.22);
    transition:background-position .35s ease, transform .18s ease, box-shadow .18s ease;
  }
  .stButton>button[kind="primary"]:hover{
    background-position:100% 50%; transform:translateY(-1px); color:#fff;
    box-shadow:0 14px 26px -14px rgba(21,110,60,1);
  }
  .stTextArea textarea{
    border-radius:12px; border:1px solid var(--line); font-size:14.5px; line-height:1.9;
    padding:14px 16px; color:var(--ink-2);
    background:linear-gradient(180deg,#FDFEFD,#FBFDFB);
  }
  .stTextArea textarea:focus{
    border-color:#84C9A0; background:#fff;
    box-shadow:0 0 0 4px rgba(58,174,106,.14), 0 1px 2px rgba(15,26,19,.04);
  }
  div[data-testid="stExpander"]{
    border:1px solid var(--line); border-radius:11px; overflow:hidden;
    background:linear-gradient(180deg,#FCFDFC,#F8FBF9);
  }
  div[data-testid="stExpander"] summary{font-size:13px; color:#4F5F55; font-weight:600;}
  div[data-testid="stExpander"] summary:hover{color:var(--green-d);}
  div[data-testid="stCode"]{border-radius:11px; max-width:100%; border:1px solid var(--line-2); overflow:hidden;}
  div[data-testid="stCode"] pre{
    white-space:pre-wrap !important; word-break:break-word; overflow-x:hidden;
    line-height:2; font-size:14px; padding-right:6px;
    background:linear-gradient(180deg,#FBFDFB,#F7FBF8);
  }
  div[data-testid="stSlider"] [data-baseweb="slider"] div[role="slider"]{
    box-shadow:0 0 0 4px rgba(58,174,106,.16), 0 2px 6px rgba(15,26,19,.2);
  }
  .stTabs [data-baseweb="tab-list"]{gap:4px; border-bottom:1px solid var(--line);}
  .stTabs [data-baseweb="tab"]{
    border-radius:9px 9px 0 0; padding:8px 16px; font-weight:600; font-size:13.5px; color:var(--muted);
  }
  .stTabs [aria-selected="true"]{
    background:var(--grad-text); -webkit-background-clip:text; background-clip:text; color:transparent;
  }
  .stTabs [data-baseweb="tab-highlight"]{background:linear-gradient(90deg,#1B7A43,#4FBB7B);}

  /* 侧栏 */
  div[data-testid="stSidebar"]{
    background:linear-gradient(180deg,#F7FBF8 0%,#F2F8F4 55%,#F8FCF9 100%);
    border-right:1px solid #E7F0EA;
  }
  .hm-card{
    background:linear-gradient(180deg,#FFFFFF,#F6FBF8);
    border:1px solid #E1EDE5; border-radius:14px; padding:18px 20px;
    box-shadow:0 1px 2px rgba(15,26,19,.04), inset 0 1px 0 #fff;
  }

  .hm-foot{
    margin-top:34px; padding-top:16px; display:flex; gap:14px; flex-wrap:wrap;
    font-size:11.5px; letter-spacing:.3px; color:var(--muted-2); position:relative;
  }
  .hm-foot:before{
    content:""; position:absolute; left:0; right:0; top:0; height:1px;
    background:linear-gradient(90deg,transparent,#DCE9E0 18%,#DCE9E0 82%,transparent);
  }
  .hm-foot b{color:#6E7E73; font-weight:600;}
  @media (max-width:720px){
    .hm-hero{padding:24px 22px; border-radius:18px;}
    .hm-hero h1{font-size:23px;}
    .hm-step{min-width:100%;}
  }
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
<div class="hm-hero"><div class="hm-hero-in">
  <div class="hm-eyebrow"><i></i>Taobao · PDD · JD 合规校验</div>
  <h1>花木文案合规校验</h1>
  <p>通用底座 + 平台差异层：一行一条粘贴整场脚本，自动标红、给依据、出改写</p>
  <div class="hm-chips">
    <span class="hm-chip"><b>{len(universal)}</b> 条通用规则</span>
    <span class="hm-chip"><b>{len(platform_only)}</b> 条平台专属</span>
    <span class="hm-chip"><b>{len(categories)}</b> 个类别</span>
    <span class="hm-chip">未命中不调用模型</span>
  </div>
</div></div>
""",
    unsafe_allow_html=True,
)

# 平台选择：all = 通用底座，其余叠加该平台的差异层规则
_pname_to_code = {v: k for k, v in platforms.items()}
st.markdown(
    '<div class="hm-plat"><span class="lb">校验平台</span><span class="line"></span></div>',
    unsafe_allow_html=True,
)
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

    if not result:
        st.markdown(
            """
<div class="hm-empty">
  <h3>粘贴脚本，开始体检</h3>
  <p>一行一条，一次可以跑完整场口播稿</p>
  <div class="hm-steps">
    <div class="hm-step"><b>STEP 01</b><span>选平台<br>通用 / 淘宝 / 拼多多 / 京东</span></div>
    <div class="hm-step"><b>STEP 02</b><span>粘贴文案<br>每行一条，自动去空行</span></div>
    <div class="hm-step"><b>STEP 03</b><span>看结果<br>依据 + 推荐修改 + 合规改写</span></div>
  </div>
</div>
""",
            unsafe_allow_html=True,
        )

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

            col_a, col_b = st.columns([1, 0.42])
            col_a.markdown(
                f'<div class="hm-section"><h2>逐条结果</h2>'
                f'<span class="cnt">{len(items)} 条</span>'
                f'<span class="hint">同一条文案的全部命中已按风险降序</span></div>',
                unsafe_allow_html=True,
            )
            for item in items:
                hits = item["hits"]
                if not hits:
                    with st.container(border=True):
                        st.markdown(
                            f'<div class="hm-head"><span class="hm-idx">#{item["idx"]:02d}</span>'
                            f'<span class="hm-risk hm-risk-d">未命中</span>'
                            f'<span class="hm-tag cat">无需修改</span></div>'
                            f'<div class="hm-orig">{html.escape(item["text"])}</div>',
                            unsafe_allow_html=True,
                        )
                    continue

                risk = top_risk(hits)
                cats = sorted({h.get("category", "") for h in hits if h.get("category")})
                cat_txt = " · ".join(f"{c} {categories.get(c, '')}" for c in cats)
                with st.container(border=True):
                    st.markdown(
                        f'<div class="hm-head">'
                        f'<span class="hm-idx">#{item["idx"]:02d}</span>'
                        f'<span class="hm-risk {RISK_CLASS.get(risk, "hm-risk-d")}">{risk}</span>'
                        f'<span class="hm-tag">{len(hits)} 处命中</span>'
                        f'<span class="hm-tag cat">{html.escape(cat_txt)}</span>'
                        + ('<span class="hm-tag ok">已改写</span>' if item["rewritten"] else '<span class="hm-tag">仅体检</span>')
                        + f'</div><div class="hm-orig">{highlight(item["text"], hits)}</div>',
                        unsafe_allow_html=True,
                    )

                    # 推荐修改文案：按替换表直接给，不依赖模型，秒出
                    sugg = [(h["matched"], h["suggestion"]) for h in hits if h.get("suggestion")]
                    if sugg:
                        rows = "".join(
                            f'<div class="hm-sug-row"><span class="from">{html.escape(src)}</span>'
                            f'<span class="arrow">→</span>'
                            f'<span class="to">{html.escape(dst)}</span></div>'
                            for src, dst in sugg
                        )
                        st.markdown(
                            '<div class="hm-sug">'
                            '<div class="hm-sug-head"><span>推荐修改文案</span></div>'
                            f'<div class="hm-sug-body">{rows}</div></div>',
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


st.markdown(
    f"""
<div class="hm-foot">
  <b>规则库 v1.1</b>
  <span>{len(universal)} 条通用 · {len(platform_only)} 条平台专属 · {len(categories)} 个类别</span>
  <span>AI 辅助建议，发布前请人工确认</span>
</div>
""",
    unsafe_allow_html=True,
)
