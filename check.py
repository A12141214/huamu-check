"""check.py —— 沭阳花木抖音口播文案：硬规则检查 + DeepSeek 合规改写。

流程：硬规则先扫（零成本）→ 命中才调 DeepSeek 改写 → 未命中直接返回“无需改写”。
没有命中时不消耗任何 API 费用。

用法：
    python check.py "家人们看这棵桂花，四季开花，养死包赔……"
    python check.py "文案" --no-ai        # 只做规则体检，不调模型、不花钱
    python check.py "文案" --json         # 机器可读输出（hits + advice）
    python check.py --file scripts.txt    # 批量：每行一条口播，逐条检查
    python check.py --selftest            # 离线自检，不联网

环境变量：
    DEEPSEEK_API_KEY   仅命中规则后才需要（可写在项目根目录 .env，或显式传 api_key=）
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from openai import OpenAI

# Windows 控制台默认 GBK，中文输出会变乱码；强制 UTF-8，管道重定向时也一样
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RULES_PATH = os.path.join(BASE_DIR, "rules.json")
REPLACEMENTS_PATH = os.path.join(BASE_DIR, "replacements.json")

BASE_URL = "https://api.deepseek.com"
MODEL = "deepseek-chat"
MAX_TOKENS = 3000

# 风险从高到低；用于排序，让“极高”永远排在最前面
RISK_ORDER = {"极高": 0, "高": 1, "中": 2, "低": 3}

# 命中词 -> 替换分组。分组选取靠“原文实际命中片段”判断，不看规则 id。
GROUP_KEYWORDS: dict[str, tuple[str, ...]] = {
    "A_售后与成活保证": (
        "养死", "死苗", "枯死", "枯了", "养不活", "包赔", "包退", "包活", "包成活", "保活",
        "包开花", "包结果", "包发芽", "包生根", "包出苗", "全活", "补发", "冻坏", "冻死",
        "冻伤", "不赔", "不售后", "不负责", "不管", "没人赔", "自理", "发芽", "见效",
    ),
    "B_效果与生长属性": (
        "四季", "全年", "一年四季", "常年", "天天", "三季", "开花", "有花", "挂果", "结果",
        "采摘", "百日红", "320天", "永不凋谢", "花开不断", "花期最长", "永不枯萎",
        "南北方", "南北", "全国", "各地", "哪里", "哪都", "到处", "随便种",
        "浇水", "浇点水", "给点水", "见水", "沾土", "见土", "插土", "放养", "不用管", "死不了", "养不死",
    ),
    "C_品种与来源": (
        "五彩", "红粉", "中国红", "牡丹玉兰", "郁金香玉兰", "七彩", "纯蓝色", "蓝色", "绿色",
        "虚构", "进口", "原装进口", "扦插", "嫁接", "播种", "种子", "授粉", "自花", "异花",
    ),
    "D_商品展示与信息一致性": (
        "主图", "详情页", "讲解", "展示", "成熟", "成品", "AI", "P图", "合成", "修图", "胶水",
        "铁丝", "拼接", "遇水开花", "干枝", "一物一拍", "专拍", "所见即所得", "一模一样",
        "零差异", "苗数", "花剑",
    ),
    "E_绝对化与保证性用语": (
        "最低", "最便宜", "最好", "最佳", "最优", "最强", "全场", "史上", "历史", "第一", "绝对",
        "100%", "百分百", "唯一", "独家", "顶级", "首选", "国家级", "世界级", "保证",
    ),
    "F_功效与封建迷信": (
        "招财", "辟邪", "镇宅", "化煞", "转运", "旺财", "风水", "开光", "灵力", "挡灾", "消灾",
        "改运", "治疗", "治愈", "药用", "入药", "消炎", "杀菌", "降血压", "降血糖", "抗癌", "防癌",
        "保健", "养生", "医疗", "药效",
    ),
    "G_禁售品种与特殊品类": (
        "榴莲", "蓝莓籽种", "七彩草莓", "火龙果", "蓝桂苗", "银冠玉", "乌羽玉", "鸡枞", "野生",
        "兰花", "石斛", "杜鹃", "百草枯", "农药", "瘦肉精", "兽用", "处方药",
    ),
}

SYSTEM_PROMPT = """你是沭阳花木产业带抖音直播间的合规文案编辑。商家给你的口播稿可能踩了平台红线，你要在不牺牲销售节奏的前提下，把违规点改成能过审、又不夸大的说法。

改写原则：
1. 只替换违规表述，保留原文的品种、规格、价格、活动信息，一个字都不要新增或脑补。
2. 售后承诺只能落到“7天绿植险”，并且必须加“以商品详情页标注为准”的括注。除“7天绿植险”外，不得承诺任何“包赔/包退/包补发/包活/包开花/包结果”。
3. 花期、挂果期、常绿与否，只能按替换参考里的真实习性写；参考里没有的品种，就写“具体花期/习性以详情页或品种说明为准”，不要猜。
4. 不编造品种名。原文用了虚构品种名（如“五彩月季”“中国红玉兰”），改写时只提示应改用什么规范名，不要把它当成真品种继续宣传。
5. 删除绝对化用语和“全国可种/怎么养都活”这类保证性表述，改成客观、可验证的说法。
6. 保持口播感：短句、口语、有称呼（家人们/哥几个）、有节奏，不要写成公文。
7. 改写结果不得再次命中任何硬规则，也不得出现新的保证性承诺。
"""


class CheckError(RuntimeError):
    """规则库/替换表不可用，或模型输出不合预期时抛出。"""


# ========== 1. 配置加载 ==========
def _load_dotenv() -> None:
    """极简 .env 读取：只补全尚未设置的环境变量，不覆盖已有值。

    依次在 check.py 同目录、上级目录、上上级目录找 .env，
    这样本模块放在子文件夹里也能复用项目根目录的 .env。
    """
    for rel in (".", "..", os.path.join("..", "..")):
        path = os.path.normpath(os.path.join(BASE_DIR, rel, ".env"))
        if not os.path.isfile(path):
            continue
        # utf-8-sig：兼容 Windows 记事本/PowerShell 写出的带 BOM 文件
        with open(path, "r", encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        return


def _read_json(path: str) -> Any:
    if not os.path.isfile(path):
        raise CheckError(f"找不到文件：{path}")
    with open(path, "r", encoding="utf-8-sig") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as exc:
            raise CheckError(f"{os.path.basename(path)} 不是合法 JSON：{exc}") from exc


def _compile_rule(item: dict[str, Any]) -> dict[str, Any]:
    """把一条 JSON 规则编译成内部结构；正则写错在这里就报出来。"""
    rid = str(item.get("id") or "").strip()
    if not rid:
        raise CheckError(f"规则缺 id：{item!r}")
    regex = item.get("regex")
    if not hasattr(regex, "finditer"):
        # 只接受手写的 {id, pattern, ...} 字典；已编译的规则带上 regex 直接复用
        pattern = item.get("pattern")
        if not pattern:
            raise CheckError(f"规则 {rid} 缺 pattern")
        try:
            regex = re.compile(pattern)
        except re.error as exc:
            raise CheckError(f"规则 {rid} 的正则无法编译：{pattern!r}（{exc}）") from exc
    return {
        "id": rid,
        "category": str(item.get("category") or ""),
        "risk": str(item.get("risk") or "中"),
        "reason": str(item.get("reason") or ""),
        "source": str(item.get("source") or ""),
        "regex": regex,
        # manual_review：依赖跨源比对（口播 vs 详情页），正则判不了，只作为人工清单
        "manual_review": bool(item.get("manual_review")),
        # 可选扩展：命中处前后若出现这些词，则忽略该次命中（用来压误报）
        "exclude": tuple(item.get("exclude") or ()),
    }


def load_categories(path: str = RULES_PATH) -> dict[str, str]:
    """类别编号 -> 名称，例如 {"A": "售后与成活保证"}。"""
    data = _read_json(path)
    cats = data.get("categories") or {}
    return {str(k): str(v) for k, v in cats.items()}


def load_rules(path: str = RULES_PATH) -> list[dict[str, Any]]:
    """读取并编译规则库。"""
    rules = _read_json(path).get("rules")
    if not isinstance(rules, list) or not rules:
        raise CheckError("rules.json 缺少非空的 rules 数组")
    return [_compile_rule(item) for item in rules]


def load_replacements(path: str = REPLACEMENTS_PATH) -> dict[str, dict[str, str]]:
    data = _read_json(path)
    if not isinstance(data, dict) or not data:
        raise CheckError("replacements.json 为空或格式不对")
    return {k: v for k, v in data.items() if isinstance(v, dict)}


# ========== 2. 硬规则匹配 ==========
def _snippet(text: str, start: int, end: int, width: int = 10) -> str:
    """把命中位置连上下文拼出来，方便商家在稿子里定位。"""
    left = text[max(0, start - width) : start]
    right = text[end : end + width]
    return f"{left}【{text[start:end]}】{right}"


PLACEHOLDER_FILL = {
    "{品种真实花期}": "详情页标注的花期",
    "{品种真实挂果期}": "详情页标注的挂果期",
}


def fill_placeholders(text: str) -> str:
    """替换表里的占位符是给模型看的，直接展示给店员时要有可读的说法。"""
    for key, val in PLACEHOLDER_FILL.items():
        text = text.replace(key, val)
    return re.sub(r"\{[^}]{1,20}\}", "详情页标注的信息", text)


def suggest_replacement(
    matched: str,
    replacements: dict[str, dict[str, str]] | None = None,
    category: str = "",
) -> str | None:
    """给一个命中片段找出推荐修改文案。

    先精确匹配替换表的键，再退化为包含匹配（取最长的键，避免“包活”盖过“包成活”）。
    优先在本类别对应的分组里找，找不到再扫其它分组。返回前把占位符换成可读说法。
    """
    replacements = replacements if replacements is not None else load_replacements()
    group = group_name_for(category) if category else ""

    ordered: list[dict[str, str]] = []
    if group and isinstance(replacements.get(group), dict):
        ordered.append(replacements[group])
    ordered += [
        v for k, v in replacements.items() if isinstance(v, dict) and k != group
    ]

    for grp in ordered:
        if matched in grp:
            return fill_placeholders(grp[matched])

    best: tuple[str, str] | None = None
    for grp in ordered:
        for key, val in grp.items():
            if len(key) < 2:
                continue
            if key in matched or matched in key:
                if best is None or len(key) > len(best[0]):
                    best = (key, val)
    return fill_placeholders(best[1]) if best else None


def lint(
    text: str,
    rules: list[dict[str, Any]] | None = None,
    replacements: dict[str, dict[str, str]] | None = None,
) -> list[dict[str, Any]]:
    """扫一遍硬规则，返回命中列表（同一位置只报一次，按风险与位置排序）。

    传了 replacements 时，每条命中会附带 suggestion（推荐修改文案）。
    """
    rules = rules if rules is not None else load_rules()
    rules = [_compile_rule(r) for r in rules]
    hits: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int]] = set()

    for rule in rules:
        if rule["manual_review"]:
            # 跨源比对类规则（口播 vs 详情页）无法用正则判定，只进人工清单
            continue
        for m in rule["regex"].finditer(text):
            # group(0) 才是完整命中（如“冻坏不赔”），不是第一个捕获组
            matched = m.group(0)
            span = (m.start(), m.end())
            if not matched.strip():
                continue
            # 豁免词看前后各两个字，才能拦住“第一次”“第一年”这类固定搭配
            window = text[max(0, span[0] - 2) : span[1] + 4]
            if any(word in window for word in rule["exclude"]):
                continue
            if (rule["id"], *span) in seen:
                continue
            seen.add((rule["id"], *span))
            hits.append(
                {
                    "rule_id": rule["id"],
                    "category": rule["category"],
                    "risk": rule["risk"],
                    "matched": matched,
                    "start": span[0],
                    "end": span[1],
                    "context": _snippet(text, span[0], span[1]),
                    "reason": rule["reason"],
                    "source": rule["source"],
                    "suggestion": (
                        suggest_replacement(matched, replacements, rule["category"])
                        if replacements is not None
                        else None
                    ),
                }
            )

    hits.sort(key=lambda h: (RISK_ORDER.get(h["risk"], 9), h["start"]))
    return hits


def manual_review_items(
    rules: list[dict[str, Any]] | None = None,
    categories: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """manual_review 规则的清单：正则判不了，只能人工看，**不计入命中**。

    这类规则（如 R017 口播 vs 详情页跨源比对）pattern 是 "(?!)" 占位，永远不会匹配。
    显式返回出来，是为了让结果里有个“还有这些要你自己看一眼”的提示，
    而不是让商家以为全部检查通过了。
    """
    rules = rules if rules is not None else load_rules()
    categories = categories if categories is not None else load_categories()
    return [
        {
            "rule_id": r["id"],
            "category": r["category"],
            "category_name": categories.get(r["category"], ""),
            "risk": r["risk"],
            "reason": r["reason"],
            "source": r["source"],
        }
        for r in rules
        if r["manual_review"]
    ]


# ========== 3. 构建替换参考 ==========
def group_name_for(category: str, categories: dict[str, str] | None = None) -> str:
    """类别编号 -> 替换表组名，例如 "A" -> "A_售后与成活保证"。"""
    categories = categories if categories is not None else load_categories()
    name = categories.get(category, "")
    return f"{category}_{name}" if name else ""


def build_replacement_context(
    hits: list[dict[str, Any]],
    replacements: dict[str, dict[str, str]] | None = None,
    categories: dict[str, str] | None = None,
) -> dict[str, dict[str, str]]:
    """只把与命中相关的替换组拿出来，避免 prompt 过长、也避免模型被无关例句带跑。

    取组顺序：先按命中的 category 精确取（组名 A_… 到 G_…），类别缺失时再退回关键词匹配。
    """
    replacements = replacements if replacements is not None else load_replacements()
    categories = categories if categories is not None else load_categories()

    relevant: dict[str, dict[str, str]] = {}
    for h in hits:
        key = group_name_for(h.get("category", ""), categories)
        if key and key in replacements:
            relevant[key] = replacements[key]

    if not relevant:
        # 兜底：调用方没给 category（比如自定义规则）时按关键词猜
        hit_text = " ".join(h["matched"] for h in hits)
        for group, keywords in GROUP_KEYWORDS.items():
            if group in replacements and any(kw in hit_text for kw in keywords):
                relevant[group] = replacements[group]
    return relevant


# ========== 4. DeepSeek 改写 ==========
def _make_client(api_key: str | None) -> OpenAI:
    _load_dotenv()
    key = (api_key or os.getenv("DEEPSEEK_API_KEY") or "").strip()
    if not key:
        raise CheckError("缺少 DEEPSEEK_API_KEY：请设置环境变量，或在项目根目录 .env 里写 DEEPSEEK_API_KEY=sk-...")
    return OpenAI(api_key=key, base_url=BASE_URL, timeout=120, max_retries=2)


def _build_prompt(
    text: str,
    hits: list[dict[str, Any]],
    replacement_context: dict[str, Any],
    categories: dict[str, str] | None = None,
) -> str:
    categories = categories or {}
    hit_context = json.dumps(
        [
            {
                "rule_id": h["rule_id"],
                "category": categories.get(h.get("category", ""), h.get("category", "")),
                "risk": h["risk"],
                "matched": h["matched"],
                "context": h["context"],
                "reason": h["reason"],
                "source": h["source"],
            }
            for h in hits
        ],
        ensure_ascii=False,
        indent=2,
    )
    return f"""下面是一段沭阳花木抖音口播文案、硬规则命中的违规点，以及针对这些违规类型的替换参考。

【原文案】
{text}

【硬规则命中的违规点】
{hit_context}

【替换参考（优先采用这里的合规说法，但要按原文语境自然融入，不要生硬拼接）】
{json.dumps(replacement_context, ensure_ascii=False, indent=2)}

请完成两件事：

1. 【逐条说明】针对每一条命中规则，用一两句话说明它为什么可能违规。必须引用上面给出的 reason 和 source，不要自己编造依据、法条或案例。

2. 【改写文案】给出一段完整的改写后口播文案。要求：
   - 把违规表述替换为合规的、卖家口播时自然能说出口的表达；
   - 不要编造原文案中没有的品种信息、花期或生长属性；信息不足时用“具体花期/习性以详情页或品种说明为准”这类中性表述，不要猜；
   - 保留原文案的口播感和销售节奏，不要改成书面公文；
   - 改写后不得再出现任何保证性承诺（7天绿植险除外），也不得新增绝对化用语。

严格按以下格式输出：

【逐条说明】
- R00X（风险等级）：……（依据：……）

【改写文案】
……"""


def rewrite_with_deepseek(
    text: str,
    hits: list[dict[str, Any]],
    *,
    api_key: str | None = None,
    replacements: dict[str, dict[str, str]] | None = None,
    model: str = MODEL,
    temperature: float = 0.3,
    max_tokens: int = MAX_TOKENS,
    client: OpenAI | None = None,
) -> str:
    """把原文案交给 DeepSeek 改写，返回带“逐条说明 + 改写文案”的完整文本。"""
    if not hits:
        raise CheckError("没有命中规则，不需要调用模型")

    prompt = _build_prompt(text, hits, build_replacement_context(hits, replacements), load_categories())
    client = client or _make_client(api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = (response.choices[0].message.content or "").strip()
    if not content:
        raise CheckError("模型返回了空内容，可重试一次")
    return content


# ========== 5. 主流程 ==========
def check(
    text: str,
    *,
    rewrite: bool = True,
    api_key: str | None = None,
    rules: list[dict[str, Any]] | None = None,
    replacements: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """检查并（可选）改写一条文案。

    返回 {"text", "hits", "advice", "rewritten"}；未命中规则时 advice 为 None、rewritten False。
    """
    text = (text or "").strip()
    if not text:
        raise ValueError("文案不能为空")

    rules = rules if rules is not None else load_rules()
    replacements = replacements if replacements is not None else load_replacements()
    hits = lint(text, rules, replacements)

    result: dict[str, Any] = {
        "text": text,
        "hits": hits,
        "manual_review": manual_review_items(rules),
        "advice": None,
        "rewritten": False,
    }
    if not hits or not rewrite:
        return result

    result["advice"] = rewrite_with_deepseek(text, hits, api_key=api_key, replacements=replacements)
    result["rewritten"] = True
    return result


def _print_human(result: dict[str, Any]) -> None:
    categories = load_categories()
    print("=" * 56)
    print("原文案：")
    print(result["text"])
    print(f"\n硬规则命中：{len(result['hits'])} 条")

    for h in result["hits"]:
        cat = categories.get(h.get("category", ""), "")
        cat_note = f" · 类别 {h['category']} {cat}" if cat else ""
        print(f"  [{h['risk']}] {h['rule_id']}{cat_note}")
        print(f"       命中：{h['matched']}")
        print(f"       位置：{h['context']}")
        if h.get("suggestion"):
            print(f"       建议：{h['suggestion']}")
        print(f"       依据：{h['source']}")

    if not result["hits"]:
        print("\n未命中硬规则，无需调用模型改写。")
    elif not result["rewritten"]:
        print("\n已跳过 AI 改写（--no-ai），以上仅规则体检结果。")
    else:
        print("\n" + "-" * 56)
        print(result["advice"])

    manual = result.get("manual_review") or []
    if manual:
        print("\n" + "-" * 56)
        print(f"另有 {len(manual)} 条需人工复核（正则判不了，不计入上方命中数）：")
        for r in manual:
            cat = f"{r['category']} {r['category_name']}".strip()
            print(f"  {r['rule_id']}（{r['risk']} · {cat}）：{r['reason'][:46]}……")

    print("\n" + "-" * 56)
    print("提示：以上结果为 AI 辅助建议，规则出处已标注，最终发布前请人工确认。")
    print("      规则库未覆盖的语义层风险（如暗示疗效、贬低同行）仍需人工判断。")


def _selftest() -> int:
    """离线自检：只验证规则匹配与替换分组，不联网、不烧 token。"""
    rules = load_rules()
    replacements = load_replacements()

    def ids(text: str) -> list[str]:
        return [h["rule_id"] for h in lint(text, rules)]

    cases: list[tuple[str, list[str]]] = [
        # A 售后与成活保证
        ("家人们看这棵桂花，四季开花，养死包赔，全网最低价，喜欢的赶紧下单！", ["R001", "R005", "R021"]),
        ("不拍保温棉，冻坏不赔啊", ["R002"]),
        ("咱们家包成活、包开花，30天发芽", ["R003", "R003", "R004"]),
        # B 效果与生长属性
        ("玉兰四季开花，一年开三季", ["R005"]),
        ("南北方均可种植，浇水就活", ["R007", "R006"]),
        ("这花永不凋谢，花开不断", ["R008", "R008"]),
        # C 品种与来源
        ("这是五彩月季，进口品种", ["R009", "R010"]),
        ("扦插苗，也可以直接播种", ["R011"]),
        # D 商品展示
        ("主图是成熟大树，实际发种苗", ["R013"]),
        ("AI 合成了一张果实挂满枝的图", ["R014"]),
        ("用胶水把果子粘上去", ["R015"]),
        ("发货苗数和详情页不一致", ["R016"]),
        ("遇水开花，实际收到是干枝", ["R018"]),
        ("所见即所得，收到和直播间一模一样", ["R020", "R020"]),
        # E/F/G
        ("全网最低价，保证成活", ["R021", "R021"]),
        ("摆家里招财辟邪", ["R022", "R022"]),
        ("这个能降血压，还能入药", ["R023", "R023"]),
        ("卖蓝莓籽种和榴莲苗", ["R024", "R024"]),
        ("高毒农药我们也有", ["R025"]),
        # 合规文案不应命中
        ("这款月季含7天绿植险，秋季盛花，具体以详情页为准", []),
        ("产地直发，今天拍明天发，苗龄两年", []),
        # —— 误报回归：这三类说法在直播间天天出现，不能报 ——
        ("这桂花四季常绿，很好养", []),
        ("第一次养花也不怕，第一年就挂果", []),
        ("今天下单有红包活动，礼包套餐都有", []),
    ]

    failures = 0
    for text, expect in cases:
        got = ids(text)
        ok = got == expect
        failures += 0 if ok else 1
        print(f"{'PASS' if ok else 'FAIL'}  期望 {expect} 实际 {got}   {text}")

    # 关键回归：R002 必须报完整片段“冻坏不赔”，并且能带出 A_ 开头的替换组
    hit = lint("不拍保温棉，冻坏不赔啊", rules)[0]
    ok = hit["matched"] == "冻坏不赔"
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  完整命中片段（不是只有捕获组）实际 {hit['matched']!r}")

    groups = build_replacement_context([hit], replacements)
    ok = "A_售后与成活保证" in groups
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  R002 带出 A_售后与成活保证 组 实际 {list(groups)}")

    # 组名必须和类别一一对齐：每个用到的类别都要能在替换表里找到对应组
    cats = load_categories()
    expect_groups = {f"{code}_{name}" for code, name in cats.items()}
    missing = expect_groups - set(replacements)
    ok = not missing
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  替换表组名与 A–G 类别完全对齐  缺：{sorted(missing) or '无'}")

    # 多类别同时命中时，应该把多个组一起取出来
    many = lint("五彩月季包开花，招财辟邪，全网最低价", rules)
    got_groups = set(build_replacement_context(many, replacements))
    ok = {"C_品种与来源", "A_售后与成活保证", "F_功效与封建迷信", "E_绝对化与保证性用语"} <= got_groups
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  多类别命中带出多组  实际 {sorted(got_groups)}")

    # 风控：命中排序必须是“极高”在前
    ok = ids("全网最低价，养死包赔") == ["R001", "R021"]
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  按风险排序，极高优先  实际 {ids('全网最低价，养死包赔')}")

    # manual_review：只进人工清单，绝不能出现在命中里
    manual = manual_review_items(rules)
    ok = (
        [m["rule_id"] for m in manual] == ["R017"]
        and "R017" not in ids("口播说三年龄苗，详情页写五年苗")
        and check("口播说三年龄苗", rewrite=False)["manual_review"][0]["rule_id"] == "R017"
    )
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  R017 只进人工清单、不参与自动命中  实际 {[m['rule_id'] for m in manual]}")

    # 推荐修改文案：每条命中都要能给出替换建议（取不到时允许为空）
    s_hits = lint("养死包赔，四季开花，全网最低价，包开花", rules, replacements)
    got = {h["matched"]: h.get("suggestion") for h in s_hits}
    ok = (
        got.get("养死包赔", "").startswith("含7天绿植险")
        and "秋季盛花" in got.get("四季开花", "")
        and got.get("全网最低", "") == "产区直供，性价比款"
        and got.get("包开花", "") != ""
    )
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  每条命中都带推荐修改文案  实际 {got}")

    # 不在替换表里的命中，建议必须是 None，不能瞎编
    trick = [{"id": "TX", "pattern": "冷门说法", "risk": "中", "reason": "-", "source": "-"}]
    ok = lint("一句冷门说法", trick, replacements)[0]["suggestion"] is None
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  替换表没有的说法不给建议（不编造）")

    # exclude 扩展：命中但含豁免词时不报
    custom = [{"id": "T1", "pattern": "第一", "risk": "高", "reason": "-", "source": "-", "exclude": ["第一次"]}]
    ok = lint("第一次养花", custom) == [] and len(lint("全网第一", custom)) == 1
    failures += 0 if ok else 1
    print(f"{'PASS' if ok else 'FAIL'}  exclude 豁免词生效")

    print(f"\n自检结果：{'全部通过' if failures == 0 else f'{failures} 项失败'}")
    return 0 if failures == 0 else 1


def _main(argv: list[str]) -> int:
    rewrite = "--no-ai" not in argv
    as_json = "--json" in argv
    file_path: str | None = None
    words: list[str] = []

    i = 0
    while i < len(argv):
        token = argv[i]
        if token in ("--no-ai", "--json"):
            i += 1
            continue
        if token == "--file" and i + 1 < len(argv):
            file_path = argv[i + 1]
            i += 2
            continue
        if token.startswith("--file="):
            file_path = token.split("=", 1)[1]
            i += 1
            continue
        if not token.startswith("--"):
            words.append(token)
        i += 1

    texts: list[str] = []
    if file_path:
        if not os.path.isfile(file_path):
            print(f"找不到文件：{file_path}", file=sys.stderr)
            return 2
        with open(file_path, "r", encoding="utf-8-sig") as fh:
            texts = [line.strip() for line in fh if line.strip()]
    else:
        single = " ".join(words).strip() or sys.stdin.read().strip()
        texts = [single] if single else []

    if not texts:
        print(
            '用法：python check.py "家人们看这棵桂花，四季开花，养死包赔……" [--no-ai] [--json] [--file 稿件.txt]',
            file=sys.stderr,
        )
        return 2

    results = []
    for text in texts:
        try:
            results.append(check(text, rewrite=rewrite))
        except Exception as exc:  # noqa: BLE001 - CLI 入口统一兜底
            print(f"失败：{exc}", file=sys.stderr)
            return 1

    if as_json:
        payload = results if len(results) > 1 else results[0]
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for idx, result in enumerate(results):
            if idx:
                print()
            _print_human(result)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv[1:]:
        raise SystemExit(_selftest())
    raise SystemExit(_main(sys.argv[1:]))
