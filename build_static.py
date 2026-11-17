"""build_static.py —— 把 rules.json / replacements.json 编译成单文件静态页。

为什么要有这个脚本：静态页里的正则是生成出来的，不是手抄的。
改完 rules.json 跑一次 `python build_static.py`，静态页和命令行/网页版就是同一套规则，
不会出现「命令行说违规、静态页说没问题」。

产物：docs/checker.html（单文件，无任何外部依赖，可直接双击打开）
线上地址（jsDelivr 直出，无需部署）：
    https://cdn.jsdelivr.net/gh/<用户名>/<仓库>@main/docs/checker.html
"""

from __future__ import annotations

import json
import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE_DIR, "docs", "checker.html")


def load() -> tuple[list[dict], dict, dict]:
    with open(os.path.join(BASE_DIR, "rules.json"), encoding="utf-8-sig") as f:
        data = json.load(f)
    with open(os.path.join(BASE_DIR, "replacements.json"), encoding="utf-8-sig") as f:
        replacements = json.load(f)
    return data["rules"], replacements, data.get("categories", {})


def main() -> None:
    rules, replacements, categories = load()
    manual = [r for r in rules if r.get("manual_review")]

    # 只挑规则必需的字段；manual_review 的规则没有可执行正则，不进前端匹配
    slim_rules = [
        {k: r.get(k, "") for k in ("id", "category", "pattern", "risk", "reason", "source")}
        for r in rules
        if not r.get("manual_review")
    ]
    # 去掉 _note 这类非映射字段（顶层说明是字符串，不是分组）
    groups = {
        k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")}
        for k, v in replacements.items()
        if isinstance(v, dict)
    }

    payload = json.dumps(
        {"rules": slim_rules, "categories": categories, "replacements": groups},
        ensure_ascii=False,
    )
    # </script> 出现在 JSON 里会提前闭合脚本块
    payload = payload.replace("</", "<\\/")

    html = TEMPLATE.replace("/*__DATA__*/null", payload)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    size = os.path.getsize(OUT)
    print(
        f"已生成 {OUT}（{size / 1024:.1f} KB，{len(slim_rules)} 条可自动检测规则，"
        f"{len(manual)} 条需人工复核）"
    )
    print("线上地址示例：https://cdn.jsdelivr.net/gh/A12141214/huamu-check@main/docs/checker.html")


TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>花木口播文案合规体检</title>
<style>
  :root{
    --green:#2E7D32; --green-d:#1B5E20; --ink:#1F2A1F; --muted:#5f6b5f;
    --bg:#F4F7F4; --card:#fff; --line:#dde5dd;
    --very:#c62828; --high:#e65100; --mid:#f9a825;
  }
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);
       font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif}
  .wrap{max-width:860px;margin:0 auto;padding:28px 20px 60px}
  header{display:flex;align-items:center;gap:10px;margin-bottom:6px}
  h1{font-size:26px;margin:0;letter-spacing:.5px}
  .sub{color:var(--muted);font-size:14px;margin:0 0 22px}
  .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px}
  textarea{width:100%;min-height:150px;border:1px solid var(--line);border-radius:10px;
           padding:12px 14px;font:inherit;color:inherit;background:#fcfdfc;resize:vertical}
  textarea:focus{outline:2px solid #b7d8b7;border-color:var(--green)}
  .row{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}
  button{font:inherit;border-radius:10px;padding:10px 20px;cursor:pointer;border:1px solid var(--line);
         background:#fff;color:var(--ink)}
  button.primary{background:var(--green);border-color:var(--green);color:#fff;font-weight:600}
  button.primary:hover{background:var(--green-d)}
  button.ghost:hover{border-color:var(--green);color:var(--green)}
  .stats{display:flex;gap:26px;margin:22px 0 4px;flex-wrap:wrap}
  .stat b{display:block;font-size:28px;line-height:1.2}
  .stat span{color:var(--muted);font-size:13px}
  .verdict{margin:10px 0 0;padding:12px 16px;border-radius:10px;font-weight:600}
  .ok{background:#e8f5e9;color:#1B5E20}
  .bad{background:#fff4e5;color:#8a4b00}
  .copy{background:#fcfdfc;border:1px solid var(--line);border-radius:10px;
        padding:14px;white-space:pre-wrap;line-height:2;font-size:15.5px}
  mark{background:#ffd8d8;color:#a40000;padding:0 3px;border-radius:4px;font-weight:600}
  .hit{border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:12px;background:#fff}
  .hit h3{margin:0 0 6px;font-size:15px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .tag{font-size:12px;padding:2px 8px;border-radius:999px;color:#fff;font-weight:600}
  .tag.very{background:var(--very)} .tag.high{background:var(--high)} .tag.mid{background:var(--mid)}
  .hit p{margin:6px 0;font-size:14px;color:#37402f}
  .hit .src{color:var(--muted);font-size:13px}
  .sug{margin-top:8px;padding:10px 12px;background:#f3f8f3;border-left:3px solid var(--green);
       border-radius:6px;font-size:14px}
  .sug b{color:var(--green-d)}
  footer{margin-top:34px;color:var(--muted);font-size:13px;line-height:1.9}
  code{background:#eef2ee;padding:1px 5px;border-radius:4px;font-size:13px}
  @media (max-width:560px){ h1{font-size:21px} .stat b{font-size:22px} }
</style>
</head>
<body>
<div class="wrap">
  <header><span style="font-size:24px">🌿</span><h1>花木口播文案合规体检</h1></header>
  <p class="sub">粘贴抖音花木口播稿，按 6 条硬红线扫一遍。纯浏览器运行，不上传、不联网、零成本。</p>

  <div class="card">
    <textarea id="txt" placeholder="例：家人们看这棵桂花，四季开花，养死包赔，全网最低价，喜欢的赶紧下单！"></textarea>
    <div class="row">
      <button class="primary" id="run">开始体检</button>
      <button class="ghost" id="demo">填入示例</button>
      <button class="ghost" id="clear">清空</button>
    </div>
  </div>

  <div id="out"></div>

  <footer>
    规则库未覆盖的语义层风险（暗示疗效、贬低同行、虚构产地等）仍需人工确认。<br>
    需要 AI 改写（逐条说明 + 合规改写稿）请用 Streamlit 版；本页只做规则体检。<br>
    规则与 <code>rules.json</code> 同源，由 <code>build_static.py</code> 生成，改规则后需重新生成。
  </footer>
</div>

<script>
const DATA = /*__DATA__*/null;
const RISK_CLASS = {"极高":"very","高":"high","中":"mid","低":"mid"};
const RISK_ORDER = {"极高":0,"高":1,"中":2,"低":3};
const SAMPLE = "家人们看这棵桂花，四季开花，养死包赔，全网最低价，喜欢的赶紧下单！";

// 预编译正则；同时按风险排序，保证“极高”永远在最上面
const RULES = DATA.rules.map((r,i)=>({...r, re:new RegExp(r.pattern,"g"), idx:i}))
  .sort((a,b)=>(RISK_ORDER[a.risk]??9)-(RISK_ORDER[b.risk]??9) || a.idx-b.idx);

function lint(text){
  const hits=[];
  for(const rule of RULES){
    rule.re.lastIndex=0;
    let m;
    while((m=rule.re.exec(text))!==null){
      if(m[0].length===0){ rule.re.lastIndex++; continue; }
      hits.push({id:rule.id,category:rule.category,risk:rule.risk,reason:rule.reason,source:rule.source,
                 matched:m[0],start:m.index,end:m.index+m[0].length});
    }
  }
  hits.sort((a,b)=>(RISK_ORDER[a.risk]??9)-(RISK_ORDER[b.risk]??9) || a.start-b.start);
  return hits;
}

// 命中的词去替换表里找说法：先精确、再包含、再按分组关键词
function suggest(matched){
  for(const group of Object.values(DATA.replacements)){
    if(Object.prototype.hasOwnProperty.call(group, matched)) return group[matched];
  }
  for(const group of Object.values(DATA.replacements)){
    for(const key of Object.keys(group)){
      if(key.length>=2 && (matched.includes(key) || key.includes(matched))) return group[key];
    }
  }
  return null;
}

function highlight(text,hits){
  const spans=[...new Set(hits.map(h=>h.start+"-"+h.end))]
    .map(s=>s.split("-").map(Number)).sort((a,b)=>a[0]-b[0]);
  const merged=[];
  for(const [s,e] of spans){
    if(merged.length && s<=merged[merged.length-1][1]) merged[merged.length-1][1]=Math.max(merged[merged.length-1][1],e);
    else merged.push([s,e]);
  }
  let out="",cur=0;
  for(const [s,e] of merged){
    out+=esc(text.slice(cur,s))+"<mark>"+esc(text.slice(s,e))+"</mark>";
    cur=e;
  }
  return out+esc(text.slice(cur));
}

function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function render(text){
  const out=document.getElementById("out");
  const hits=lint(text);
  if(!text.trim()){ out.innerHTML=""; return; }

  if(!hits.length){
    out.innerHTML=`<div class="stats"><div class="stat"><b>0</b><span>命中条数</span></div></div>
      <div class="verdict ok">未命中硬规则 ✅　规则库未覆盖的语义风险仍需人工确认。</div>
      <div class="card" style="margin-top:16px"><div class="copy">${esc(text)}</div></div>`;
    return;
  }

  const top=hits[0].risk;
  const cards=hits.map(h=>{
    const sg=suggest(h.matched);
    const cat=DATA.categories[h.category]||"";
    return `<div class="hit">
      <h3><span class="tag ${RISK_CLASS[h.risk]||"mid"}">${h.risk}</span>
          ${h.id}${cat?` · ${esc(cat)}`:""} · 命中「${esc(h.matched)}」</h3>
      <p>${esc(h.reason)}</p>
      <p class="src">依据：${esc(h.source)}</p>
      ${sg?`<div class="sug"><b>合规说法：</b>${esc(sg)}</div>`:""}
    </div>`;
  }).join("");

  out.innerHTML=`<div class="stats">
      <div class="stat"><b>${hits.length}</b><span>命中条数</span></div>
      <div class="stat"><b>${top}</b><span>最高风险</span></div>
      <div class="stat"><b>${RULES.length}</b><span>规则总数</span></div>
    </div>
    <div class="verdict bad">发现 ${hits.length} 处可能违规，发布前请逐条核对。</div>
    <div class="card" style="margin-top:16px"><div class="copy">${highlight(text,hits)}</div></div>
    ${cards}`;
}

document.getElementById("run").onclick=()=>{
  const t=document.getElementById("txt").value;
  if(!t.trim()){ alert("请先粘贴一段文案"); return; }
  render(t);
  document.getElementById("out").scrollIntoView({behavior:"smooth",block:"start"});
};
document.getElementById("demo").onclick=()=>{
  document.getElementById("txt").value=SAMPLE; render(SAMPLE);
};
document.getElementById("clear").onclick=()=>{
  document.getElementById("txt").value=""; document.getElementById("out").innerHTML="";
  document.getElementById("txt").focus();
};
document.getElementById("txt").addEventListener("keydown",e=>{
  if((e.ctrlKey||e.metaKey)&&e.key==="Enter") document.getElementById("run").click();
});
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
