"""
Single-model web search market research client.

No API key is stored in code. The app reads configuration from environment
variables or Streamlit secrets:

- MARKET_RESEARCH_API_KEY or OPENAI_API_KEY
- MARKET_RESEARCH_API_BASE_URL, default: https://aihubmix.com/v1
- MARKET_RESEARCH_MODEL, default: deepseek-v4-flash:surfing

For AIHubMix :surfing models, this uses Chat Completions because the search
capability is enabled by the model suffix. For OpenAI official API, this uses
the Responses API with tools=[{"type": "web_search"}].
"""

from __future__ import annotations

import os
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


DEFAULT_BASE_URL = "https://aihubmix.com/v1"
DEFAULT_MODEL = "deepseek-v4-flash:surfing"
DEFAULT_MODEL_2 = "deepseek-v4-flash:surfing"
DEFAULT_MODEL_3 = "deepseek-v4-flash:surfing"
DEFAULT_MODEL_4 = "deepseek-v4-flash:surfing"
MISSING_KEY_MESSAGE = "当前未配置 MARKET_RESEARCH_API_KEY 或 OPENAI_API_KEY，无法使用联网搜索模式。"
STANDARD_SECTION_NAMES = [
    "机会总览",
    "痛点与用户",
    "市场与竞品",
    "地区策略",
    "商业化策略",
    "盈利测算",
    "增长与留存",
    "护城河与壁垒",
    "合规与风险",
    "落地风险",
    "MVP 验证",
    "特别注意",
    "最终建议",
    "来源摘要",
]
EXPLORE_SECTION_NAMES = [
    "自由探索总览",
    "最值得关注的市场机会",
    "最可能被忽视的用户痛点",
    "最危险的反例或失败风险",
    "可能的产品切入方向",
    "建议下一步验证什么",
    "最终判断",
    "来源摘要",
]
SECTION_NAMES = STANDARD_SECTION_NAMES + [name for name in EXPLORE_SECTION_NAMES if name not in STANDARD_SECTION_NAMES]


@dataclass
class WebModelConfig:
    role_key: str
    role_name: str
    model: str
    focus: str


@dataclass
class WebMarketResearchResult:
    status: str
    model: str
    base_url: str
    role_key: str = ""
    role_name: str = ""
    focus: str = ""
    content: str = ""
    sources: list[str] = field(default_factory=list)
    error: str = ""
    search_detected: bool = False
    sections: dict[str, str] = field(default_factory=dict)


@dataclass
class MultiWebMarketResearchResult:
    outputs: list[WebMarketResearchResult]
    base_url: str
    sources: list[str] = field(default_factory=list)
    research_structure: str = "standard"


def default_model_configs(model_1: str = "", model_2: str = "", model_3: str = "") -> list[WebModelConfig]:
    return [
        WebModelConfig(
            role_key="market",
            role_name="市场机会研究专家",
            model=model_1.strip() or os.getenv("MARKET_RESEARCH_MODEL_1", "").strip() or DEFAULT_MODEL,
            focus="市场价值、行业趋势、地区机会、商业化潜力、市场规模证据",
        ),
        WebModelConfig(
            role_key="product",
            role_name="产品与竞品研究专家",
            model=model_2.strip() or os.getenv("MARKET_RESEARCH_MODEL_2", "").strip() or DEFAULT_MODEL_2,
            focus="目标用户、使用场景、竞品与替代方案、差异化和产品闭环",
        ),
        WebModelConfig(
            role_key="risk",
            role_name="红队风险与验证专家",
            model=model_3.strip() or os.getenv("MARKET_RESEARCH_MODEL_3", "").strip() or DEFAULT_MODEL_3,
            focus="伪需求风险、合规风险、落地风险、反例和 MVP 验证",
        ),
    ]


def default_summary_config(model_4: str = "") -> WebModelConfig:
    return WebModelConfig(
        role_key="summary",
        role_name="总结专家",
        model=model_4.strip() or os.getenv("MARKET_RESEARCH_MODEL_4", "").strip() or DEFAULT_MODEL_4,
        focus="综合前三个模型的结论，提炼简洁、清晰、可决策的核心判断",
    )


def get_api_key(explicit_api_key: str = "") -> str:
    _load_dotenv_if_available()
    key = explicit_api_key.strip() or os.getenv("MARKET_RESEARCH_API_KEY", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return key
    try:
        import streamlit as st

        return str(st.secrets.get("MARKET_RESEARCH_API_KEY") or st.secrets.get("OPENAI_API_KEY") or "").strip()
    except Exception:
        return ""


def get_base_url(explicit_base_url: str = "") -> str:
    _load_dotenv_if_available()
    value = explicit_base_url.strip() or os.getenv("MARKET_RESEARCH_API_BASE_URL", "").strip()
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get("MARKET_RESEARCH_API_BASE_URL") or DEFAULT_BASE_URL).strip()
    except Exception:
        return DEFAULT_BASE_URL


def get_model(explicit_model: str = "") -> str:
    _load_dotenv_if_available()
    value = explicit_model.strip() or os.getenv("MARKET_RESEARCH_MODEL", "").strip()
    if value:
        return value
    try:
        import streamlit as st

        return str(st.secrets.get("MARKET_RESEARCH_MODEL") or DEFAULT_MODEL).strip()
    except Exception:
        return DEFAULT_MODEL


def has_api_key(explicit_api_key: str = "") -> bool:
    return bool(get_api_key(explicit_api_key))


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


def run_multi_model_market_research(
    *,
    product_name: str,
    product_type: str,
    idea_text: str,
    api_key: str = "",
    base_url: str = "",
    model_configs: list[WebModelConfig] | None = None,
    research_structure: str = "standard",
) -> MultiWebMarketResearchResult:
    api_key = get_api_key(api_key)
    base_url = get_base_url(base_url)
    configs = model_configs or default_model_configs()
    if not api_key:
        outputs = [
            WebMarketResearchResult(
                status="未执行",
                model=config.model,
                base_url=base_url,
                role_key=config.role_key,
                role_name=config.role_name,
                focus=config.focus,
                error=MISSING_KEY_MESSAGE,
            )
            for config in configs
        ]
        return MultiWebMarketResearchResult(outputs=outputs, base_url=base_url, research_structure=research_structure)

    outputs: list[WebMarketResearchResult] = []
    # AIHubMix :surfing models often close connections when multiple search calls
    # are fired at the same time. Run roles sequentially for reliability.
    for config in configs:
        try:
            outputs.append(
                run_web_market_research(
                    product_name=product_name,
                    product_type=product_type,
                    idea_text=idea_text,
                    api_key=api_key,
                    base_url=base_url,
                    model=config.model,
                    model_config=config,
                    research_structure=research_structure,
                )
            )
        except Exception as exc:
            outputs.append(
                WebMarketResearchResult(
                    status="搜索失败，需要人工核查。",
                    model=config.model,
                    base_url=base_url,
                    role_key=config.role_key,
                    role_name=config.role_name,
                    focus=config.focus,
                    error=str(exc),
                )
            )
        time.sleep(0.8)
    role_order = {config.role_key: index for index, config in enumerate(configs)}
    outputs.sort(key=lambda item: role_order.get(item.role_key, 99))
    sources: list[str] = []
    for output in outputs:
        for source in output.sources:
            if source not in sources:
                sources.append(source)
    return MultiWebMarketResearchResult(outputs=outputs, base_url=base_url, sources=sources, research_structure=research_structure)


def run_web_market_research(
    *,
    product_name: str,
    product_type: str,
    idea_text: str,
    api_key: str = "",
    base_url: str = "",
    model: str = "",
    model_config: WebModelConfig | None = None,
    research_structure: str = "standard",
) -> WebMarketResearchResult:
    api_key = get_api_key(api_key)
    base_url = get_base_url(base_url)
    model = get_model(model)
    if not api_key:
        return WebMarketResearchResult(
            status="未执行",
            model=model,
            base_url=base_url,
            role_key=model_config.role_key if model_config else "",
            role_name=model_config.role_name if model_config else "",
            focus=model_config.focus if model_config else "",
            error=MISSING_KEY_MESSAGE,
        )

    try:
        if _should_use_surfing_chat(base_url, model):
            return _call_surfing_chat(model, base_url, product_name, product_type, idea_text, api_key, model_config, research_structure)

        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        return _call_openai_responses_search(client, model, base_url, product_name, product_type, idea_text, model_config, research_structure)
    except Exception as exc:
        return WebMarketResearchResult(
            status="搜索失败，需要人工核查。",
            model=model,
            base_url=base_url,
            role_key=model_config.role_key if model_config else "",
            role_name=model_config.role_name if model_config else "",
            focus=model_config.focus if model_config else "",
            error=str(exc),
            search_detected=False,
        )


def run_summary_expert(
    *,
    product_name: str,
    product_type: str,
    idea_text: str,
    outputs: list[WebMarketResearchResult],
    api_key: str = "",
    base_url: str = "",
    model: str = "",
) -> WebMarketResearchResult:
    api_key = get_api_key(api_key)
    base_url = get_base_url(base_url)
    config = default_summary_config(model)
    if not api_key:
        return WebMarketResearchResult(
            status="未执行",
            model=config.model,
            base_url=base_url,
            role_key=config.role_key,
            role_name=config.role_name,
            focus=config.focus,
            error=MISSING_KEY_MESSAGE,
        )

    content_blocks = []
    for output in outputs:
        if output.error:
            content_blocks.append(f"## {output.role_name}\n调用失败：{output.error}")
        else:
            content_blocks.append(f"## {output.role_name}\n{output.content}")

    payload = {
        "model": config.model,
        "stream": False,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "你是产品战略总结专家。你不需要重新展开长篇调研，只负责综合多个模型的结果，给出简洁、清晰、可执行的最终判断。",
            },
            {
                "role": "user",
                "content": _build_summary_prompt(
                    product_name=product_name,
                    product_type=product_type,
                    idea_text=idea_text,
                    combined_research="\n\n".join(content_blocks),
                ),
            },
        ],
    }
    try:
        raw = _post_chat_completion(base_url=base_url, api_key=api_key, payload=payload)
        content = str(raw.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        return WebMarketResearchResult(
            status="已完成总结",
            model=config.model,
            base_url=base_url,
            role_key=config.role_key,
            role_name=config.role_name,
            focus=config.focus,
            content=content,
            sources=_extract_sources(raw),
            search_detected=False,
            sections=_split_markdown_sections(content),
        )
    except Exception as exc:
        return WebMarketResearchResult(
            status="总结失败",
            model=config.model,
            base_url=base_url,
            role_key=config.role_key,
            role_name=config.role_name,
            focus=config.focus,
            error=str(exc),
        )


def _should_use_surfing_chat(base_url: str, model: str) -> bool:
    return "aihubmix" in base_url.lower() or model.lower().endswith(":surfing")


def _call_surfing_chat(
    model: str,
    base_url: str,
    product_name: str,
    product_type: str,
    idea_text: str,
    api_key: str,
    model_config: WebModelConfig | None,
    research_structure: str,
) -> WebMarketResearchResult:
    payload = {
        "model": model,
        "stream": False,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是资深市场部经理和早期产品机会研究专家。当前模型应通过 :surfing 搜索增强联网检索。"
                    "必须主动结合外部搜索，不要只基于用户输入推理；不要编造来源。"
                    f"你的角色是：{model_config.role_name if model_config else '市场研究专家'}。"
                    f"你的重点视角是：{model_config.focus if model_config else '综合市场机会研究'}。"
                ),
            },
            {"role": "user", "content": _build_prompt(product_name=product_name, product_type=product_type, idea_text=idea_text, model_config=model_config, research_structure=research_structure)},
        ],
    }
    raw = _post_chat_completion(base_url=base_url, api_key=api_key, payload=payload)
    content = str(raw.get("choices", [{}])[0].get("message", {}).get("content") or "")
    sources = _extract_sources(raw)
    search_detected = model.lower().endswith(":surfing") and bool(content.strip())
    return WebMarketResearchResult(
        status="已调用 :surfing 搜索增强模型" if search_detected else "已返回，但未检测到搜索调用或来源",
        model=model,
        base_url=base_url,
        role_key=model_config.role_key if model_config else "",
        role_name=model_config.role_name if model_config else "",
        focus=model_config.focus if model_config else "",
        content=content.strip(),
        sources=sources,
        search_detected=search_detected,
        sections=_split_markdown_sections(content),
    )


def _post_chat_completion(*, base_url: str, api_key: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = base_url.rstrip("/") + "/chat/completions"
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    last_error = ""

    for attempt in range(1, 4):
        request = urllib.request.Request(
            url=url,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Connection": "close",
                "User-Agent": "market-research-demo/1.0",
            },
            method="POST",
        )
        try:
            # Ignore broken system proxy variables such as HTTP_PROXY=http://127.0.0.1:9.
            with opener.open(request, timeout=180) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as exc:
            last_error = str(exc)
            if attempt < 3:
                time.sleep(1.5 * attempt)
                continue
            raise RuntimeError(f"网络请求失败，已重试 {attempt} 次：{last_error}") from exc

    raise RuntimeError(f"网络请求失败：{last_error}")


def _call_openai_responses_search(
    client: Any,
    model: str,
    base_url: str,
    product_name: str,
    product_type: str,
    idea_text: str,
    model_config: WebModelConfig | None,
    research_structure: str,
) -> WebMarketResearchResult:
    response = client.responses.create(
        model=model,
        tools=[{"type": "web_search", "search_context_size": "medium"}],
        tool_choice="required",
        include=["web_search_call.action.sources"],
        input=_build_prompt(product_name=product_name, product_type=product_type, idea_text=idea_text, model_config=model_config, research_structure=research_structure),
    )
    raw = response.model_dump() if hasattr(response, "model_dump") else response
    content = getattr(response, "output_text", "") or _extract_text(raw)
    sources = _extract_sources(raw)
    search_detected = _has_web_search_call(raw) or bool(sources)
    return WebMarketResearchResult(
        status="已完成联网市场调研" if search_detected else "已返回，但未检测到搜索调用或来源",
        model=model,
        base_url=base_url,
        role_key=model_config.role_key if model_config else "",
        role_name=model_config.role_name if model_config else "",
        focus=model_config.focus if model_config else "",
        content=content.strip(),
        sources=sources,
        search_detected=search_detected,
        sections=_split_markdown_sections(content),
    )


def _build_prompt(
    *,
    product_name: str,
    product_type: str,
    idea_text: str,
    model_config: WebModelConfig | None = None,
    research_structure: str = "standard",
) -> str:
    idea_text = _compact_idea_text(idea_text)
    if research_structure == "explore":
        return _build_exploration_prompt(product_name=product_name, product_type=product_type, idea_text=idea_text, model_config=model_config)
    return f"""
你是资深市场部经理和早期产品机会研究专家。请对下面的产品想法进行真实联网搜索市场调研。

产品名称：{product_name or "输入中未说明"}
产品类型：{product_type}
产品想法：
{idea_text}

你的角色：{model_config.role_name if model_config else "市场研究专家"}
你的分析重点：{model_config.focus if model_config else "综合市场机会研究"}

强制要求：
1. 必须使用联网搜索结果，不要只基于用户输入推理。
2. 搜索时优先寻找行业研究报告、咨询公司报告、白皮书、监管/政府公开数据、平台公开数据、上市公司年报/财报/招股书、权威媒体深度报道。
3. 如果找到数据支撑，请写出具体数据、年份、地区/样本口径和来源名称；如果口径不清楚，必须标注“口径需核查”。
4. 不要编造市场数据、报告名、竞品名称、链接或来源。
5. 如果搜索结果不足，明确写“搜索结果不足，需要人工补充资料”。
6. 明确区分：用户输入、联网搜索信息、模型推理、待验证假设。
7. 输出中文 Markdown。
8. 每个二级标题章节末尾都必须包含一个三级标题“### 引用来源”，列出本章节引用的报告/网页/数据来源；如果拿到 URL，请使用 Markdown 超链接格式；如果没有可靠来源，写“搜索结果不足，需要人工补充资料”。
9. 每个二级标题下面第一行必须先写“**核心发现：**”，用 1-2 句话概括本章节最重要的判断；核心发现必须是归纳结论，不要写表头、目录、字段名或流水账。核心发现之后再展开详细论述、表格和引用来源。

请严格按以下 Markdown 二级标题输出，每个标题必须原样保留：
## 机会总览
## 痛点与用户
## 市场与竞品
## 地区策略
## 商业化策略
## 盈利测算
## 增长与留存
## 护城河与壁垒
## 合规与风险
## 落地风险
## MVP 验证
## 特别注意
## 最终建议
## 来源摘要

各章节分析重点：
- 机会总览：必须包含“市场价值评分（1-10分）”“是否值得推进（值得推进/谨慎推进/暂不建议推进）”“核心目标人群”“优先首发市场”“推荐推进路径”“一句话理由”。评分要基于联网搜索证据和商业逻辑，不能只给空泛判断。
- 盈利测算：用通俗方式分析这个项目怎么赚钱，包括收入模型、毛利结构、获客成本、回本周期、复购/续费可能性、早期最应监控的经济指标。
- 增长与留存：用户从哪里来、为什么留下、首个 aha moment、使用频率、留存机制、口碑/推荐可能性。
- 护城河与壁垒：数据壁垒、工作流嵌入、品牌信任、渠道壁垒、供应链/服务壁垒、差异化被复制的风险。
- 合规与风险：数据隐私、内容安全、行业监管、跨境合规、知识产权、平台政策、需要法律/专业人士核查的问题。
- 特别注意：这是自由探索和反常识补充区，不要重复前面章节已经覆盖的常规分析。请重点回答这些问题：
  1. 这个想法最容易被忽视的机会是什么？
  2. 这个想法最危险的反例是什么，哪些真实失败案例或用户反馈会推翻它？
  3. 有没有比用户原始设想更好的切入场景？
  4. 有没有需要重新定义的目标用户，谁可能比原始目标用户更痛、更愿意付费或更容易触达？
  5. 有没有和用户原始想法不同但更可行的产品方向？
  6. 有没有被现有结构遗漏的渠道、合规、生态位、供应链、平台政策或时机窗口？
  输出时请用“小标题 + 结论 + 证据/推理 + 需要验证的问题”的结构，明确哪些是搜索证据，哪些是模型推断。
- 来源引用格式：报告或网页名称｜发布方｜年份｜核心引用数据或观点｜[链接](URL)。如果模型无法拿到链接，也要说明“未返回链接，需人工核查”。
""".strip()


def _build_exploration_prompt(*, product_name: str, product_type: str, idea_text: str, model_config: WebModelConfig | None = None) -> str:
    return f"""
你是资深市场部经理和早期产品机会研究专家。请对下面的早期产品想法进行自由探索式联网市场调研。

产品名称：{product_name or "输入中未说明"}
产品类型：{product_type}
产品想法：
{idea_text}

你的角色：{model_config.role_name if model_config else "市场研究专家"}
你的分析重点：{model_config.focus if model_config else "综合市场机会研究"}

这是 B 版：自由探索版。
目标不是按固定维度填表，也不要按固定章节补齐内容。请先判断用户输入属于哪一种：
- 如果输入是“具体产品/项目想法”，请判断这个项目是否值得继续做。
- 如果输入是“趋势、现象、行业变化或市场机会问题”（例如“Agent 正在替代人们的工作，会有什么市场机会？”），请不要硬套“项目是否值得推进”，而是输出这个趋势下最值得探索的产品机会、目标用户、切入场景和优先级。

强制要求：
1. 必须使用联网搜索结果，不要只基于用户输入推理。
2. 搜索时优先寻找行业研究报告、咨询公司报告、白皮书、监管/政府公开数据、平台公开数据、上市公司年报/财报/招股书、权威媒体深度报道和真实失败案例。
3. 不要编造市场数据、报告名、竞品名称、链接或来源。
4. 明确区分：用户输入、联网搜索信息、模型推理、待验证假设。
5. 不要输出固定模板，不要为了覆盖维度而机械分章节。你可以自由组织内容，重点是洞察质量和判断力度。
6. 开头必须先说明“输入类型”：具体产品评估 / 趋势机会探索。
7. 如果是具体产品评估，开头给出“值得继续 / 需要调整 / 暂缓”之一，并用一句话说明理由。
8. 如果是趋势机会探索，开头给出“最值得优先探索的 3 个机会方向”，不要写“值得继续”这种项目推进结论。
9. 然后自由展开你的市场调研发现：可以包括你认为最关键的市场机会、被忽视的痛点、危险反例、更好的切入场景、目标用户重定义、竞品或替代方向、低成本验证方式等，但不要求按这些标题逐项写。
10. 如果拿到 URL，请使用 Markdown 超链接格式；如果没有可靠来源，写“搜索结果不足，需要人工补充资料”。
11. 输出中文 Markdown，内容要适合创业者或产品负责人直接阅读和决策。
12. 不要输出“如果你愿意，我可以继续……” “需要你确认后我再……” “我可以下一步帮你……”这类对话式邀请。本 Demo 不是连续聊天界面，用户不能在结果里继续追问。请把你建议的下一步直接写成明确、可执行的行动清单。
""".strip()


def _build_summary_prompt(*, product_name: str, product_type: str, idea_text: str, combined_research: str) -> str:
    return f"""
请综合下面三个模型的市场调研结果，输出一份让产品负责人一眼能看懂的核心结论。

产品名称：{product_name or "输入中未说明"}
产品类型：{product_type}
用户输入的产品想法：
{_compact_idea_text(idea_text, limit=2500)}

三个模型的调研结果：
{_compact_idea_text(combined_research, limit=12000)}

输出要求：
1. 不要复述三个模型的长篇内容。
2. 不要输出“如果你愿意我可以继续”这类对话式内容。
3. 语言要简洁、直接、适合老板或产品负责人快速判断。
4. 先判断用户输入类型：具体产品评估 / 趋势机会探索。
5. 如果是具体产品评估，必须包含：
   - 最终判断：值得推进 / 需要调整 / 暂缓
   - 一句话结论
   - 最核心的 3 条理由
   - 最大风险
   - 最推荐的目标用户
   - 最推荐的切入场景
   - 下一步 3 个动作
6. 如果是趋势机会探索，不要写“值得推进”这种项目结论，必须包含：
   - 一句话趋势判断
   - 最值得优先探索的 3 个产品机会方向
   - 每个机会对应的目标用户和典型场景
   - 最容易踩坑的伪机会
   - 下一步应该验证的 3 件事
7. 输出中文 Markdown，控制在 600 字以内。
""".strip()


def _compact_idea_text(idea_text: str, limit: int = 9000) -> str:
    text = (idea_text or "").strip()
    if len(text) <= limit:
        return text
    head = text[: int(limit * 0.7)]
    tail = text[-int(limit * 0.3) :]
    return f"{head}\n\n[输入材料较长，中间部分已为稳定联网调用压缩省略]\n\n{tail}"


def _extract_text(data: Any) -> str:
    texts: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") in {"output_text", "text"} and isinstance(value.get("text"), str):
                texts.append(value["text"])
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return "\n".join(texts)


def _extract_sources(data: Any) -> list[str]:
    sources: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            title = str(value.get("title") or value.get("name") or "").strip()
            url = str(value.get("url") or value.get("uri") or "").strip()
            if url:
                source = f"{title} - {url}" if title else url
                if source not in sources:
                    sources.append(source)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return sources[:30]


def _has_web_search_call(data: Any) -> bool:
    found = False

    def walk(value: Any) -> None:
        nonlocal found
        if found:
            return
        if isinstance(value, dict):
            if "web_search" in str(value.get("type") or ""):
                found = True
                return
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(data)
    return found


def _split_markdown_sections(content: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in (content or "").splitlines():
        stripped = line.strip()
        heading_match = re.match(r"^#{1,4}\s+(.+?)\s*$", stripped)
        if heading_match:
            title = _normalize_section_title(heading_match.group(1))
            if title:
                current = title
                sections.setdefault(current, [])
                continue
        if current:
            sections.setdefault(current, []).append(line)
    return {name: "\n".join(lines).strip() for name, lines in sections.items() if "\n".join(lines).strip()}


def _normalize_section_title(title: str) -> str:
    cleaned = title.strip()
    cleaned = re.sub(r"[*_`#：:]+", "", cleaned).strip()
    cleaned = re.sub(r"^(第?[一二三四五六七八九十]+[章节部分]?|[0-9]+)\s*[、.．)\-—]\s*", "", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    if "单位经济" in cleaned:
        return "盈利测算"
    for section_name in SECTION_NAMES:
        if cleaned == section_name or cleaned.startswith(section_name) or section_name in cleaned:
            return section_name
    return ""
