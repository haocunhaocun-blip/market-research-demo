from __future__ import annotations

import re
from dataclasses import asdict
from typing import Literal

from src.consensus import arbitrate_all
from src.mock_agents import run_all_agents
from src.real_agents import run_all_real_agents
from src.report_generator import (
    build_markdown_report,
    build_mvp_validation_plan,
    build_product_scores,
    build_thirty_day_plan,
    decide_final_recommendation,
)
from src.schemas import UNKNOWN_RESEARCHED, FinalReport, MarketAnalysis, PRDSummary


AgentMode = Literal["mock", "aihubmix_normal", "aihubmix_search", "aihubmix_surfing"]

RESEARCH_TOPICS = [
    "这个产品想法解决的核心痛点是什么？",
    "这个痛点是否真实存在？",
    "哪些用户群体最可能有这个痛点？",
    "这些用户当前用什么替代方案解决问题？",
    "市场上是否已有相似产品或竞品？",
    "当前市场趋势是否支持这个产品方向？",
    "这个产品的差异化机会在哪里？",
    "用户是否可能愿意付费？",
    "适合 To C、To B，还是 To B + To C 混合模式？",
    "中国市场机会如何？",
    "北美市场机会如何？",
    "欧洲市场机会如何？",
    "哪个地区更适合作为首发市场？",
    "应该采用什么市场进入策略？",
    "产品最小可行版本 MVP 应该是什么？",
    "哪些关键假设需要优先验证？",
    "这个项目当前是否值得继续推进？",
]


def run_research_pipeline(
    prd_text: str,
    product_name: str = "",
    product_type: str = "其他",
    agent_mode: AgentMode = "mock",
    model_overrides: dict[str, str] | None = None,
) -> FinalReport:
    prd_summary = parse_idea(prd_text, product_name)
    research_topics = build_research_topics(product_type)

    agent_outputs = []
    for topic in research_topics:
        if agent_mode != "mock":
            run_mode = {
                "aihubmix_normal": "normal",
                "aihubmix_search": "web_search",
                "aihubmix_surfing": "surfing",
            }[agent_mode]
            agent_outputs.extend(
                run_all_real_agents(topic, prd_summary, run_mode=run_mode, model_overrides=model_overrides)
            )
        else:
            agent_outputs.extend(run_all_agents(topic, prd_summary))

    consensus_report = arbitrate_all(agent_outputs)
    market_analysis = analyze_markets(prd_summary, agent_outputs)
    mvp_plan = build_mvp_validation_plan(consensus_report, market_analysis)
    thirty_day_plan = build_thirty_day_plan()
    product_scores = build_product_scores(consensus_report, market_analysis)
    final_recommendation = decide_final_recommendation(product_scores, consensus_report)
    markdown_report = build_markdown_report(
        prd_summary=prd_summary,
        research_topics=research_topics,
        consensus_report=consensus_report,
        agent_outputs=agent_outputs,
        market_analysis=market_analysis,
        mvp_validation_plan=mvp_plan,
        thirty_day_plan=thirty_day_plan,
        product_scores=product_scores,
        final_recommendation=final_recommendation,
    )

    return FinalReport(
        prd_summary=prd_summary,
        research_topics=research_topics,
        agent_outputs=agent_outputs,
        market_analysis=market_analysis,
        consensus_report=consensus_report,
        mvp_validation_plan=mvp_plan,
        thirty_day_plan=thirty_day_plan,
        final_recommendation=final_recommendation,
        markdown_report=markdown_report,
        product_scores=product_scores,
    )


def parse_idea(idea_text: str, product_name: str = "") -> PRDSummary:
    text = _normalize(idea_text)
    summary = PRDSummary()
    summary.product_name = product_name.strip() or _extract_value(text, ["产品名称", "项目名称", "名称"]) or "输入中未说明，已转化为外部调研问题：产品命名"
    summary.product_positioning = (
        _extract_value(text, ["一句话定位", "产品定位", "定位", "愿景", "产品想法", "背景"])
        or _infer_positioning(text)
    )
    summary.core_features = _extract_list(text, ["核心功能", "主要功能", "功能列表", "功能", "解决方案"])
    summary.target_users = _extract_value(text, ["目标用户", "用户群体", "目标客户", "受众", "客群"]) or _infer_target_users(text)
    summary.use_cases = _extract_list(text, ["使用场景", "应用场景", "场景", "痛点", "需求"])
    summary.business_goals = _extract_value(text, ["商业目标", "商业模式", "收入模式", "定价", "商业化"])
    summary.technical_dependencies = _extract_list(text, ["技术依赖", "技术方案", "依赖", "架构"])
    summary.potential_risks = _extract_list(text, ["潜在风险", "风险", "挑战", "限制"])

    _fill_missing_lists(summary)
    summary.missing_information = _missing_fields(summary)
    return summary


parse_prd = parse_idea


def build_research_topics(product_type: str) -> list[str]:
    topics = list(RESEARCH_TOPICS)
    if product_type and product_type not in {"其他", ""}:
        topics.insert(0, f"{product_type}品类适配性与进入门槛判断")
    return topics


def analyze_markets(prd_summary: PRDSummary, agent_outputs: list | None = None) -> list[MarketAnalysis]:
    regions = ["中国市场", "北美市场", "欧洲市场"]
    analyses = [_build_market(region, prd_summary, agent_outputs or []) for region in regions]
    analyses.append(_build_global_strategy(analyses))
    return analyses


def _build_market(region: str, summary: PRDSummary, agent_outputs: list) -> MarketAnalysis:
    base = 5
    if not _is_unknown(summary.target_users):
        base += 1
    if summary.use_cases and not _list_is_unknown(summary.use_cases):
        base += 1
    if not _is_unknown(summary.business_goals):
        base += 1
    if _has_search_evidence(agent_outputs):
        base += 1
    region_adjustment = {"中国市场": 0, "北美市场": 1, "欧洲市场": -1}.get(region, 0)
    score = max(1, min(10, base + region_adjustment))
    priority = "P1" if score >= 7 else "P2" if score >= 5 else "P3"

    entry_method = {
        "中国市场": "内容种草、私域访谈、小范围灰度试用、电商或企业渠道验证",
        "北美市场": "Landing Page、Product Hunt/Reddit/垂直社区冷启动、众筹或订阅意向测试",
        "欧洲市场": "垂直社区验证、合规先行评估、B2B 小样本试点",
    }[region]
    evidence = _source_note(agent_outputs)

    return MarketAnalysis(
        market_region=region,
        demand_fit=f"基于用户输入和 Agent 研究，可能存在需求匹配；需验证当地用户是否高频遇到：{_list_preview(summary.use_cases)}。来源类型：{evidence}",
        willingness_to_pay="付费意愿不能仅靠想法判断；建议用价格锚点、预售、等候名单或 B2B 采购意向验证。来源类型：模型推理；待验证假设。",
        channel_feasibility=f"可优先尝试{entry_method}。来源类型：模型推理；市场进入假设。",
        competition_pressure="需要按地区补充直接竞品、间接竞品、人工流程和现有工具替代方案。来源类型：竞品信息；联网搜索；待验证假设。",
        compliance_risk="如涉及隐私、AI、摄像头、音频、儿童、医疗、金融、数据跨境或硬件认证，需要单独合规评估。来源类型：模型推理；待验证假设。",
        localization_difficulty="需要根据语言、文化表达、工作流、支付方式、交付和售后预期做本地化调整。",
        launch_fit_score=score,
        advantages=_market_advantages(region),
        disadvantages=_market_disadvantages(region),
        key_risks=["搜索结果不足时需人工补充资料", "真实获客成本未知", "本地竞品和合规要求未完全验证"],
        recommended_entry_method=entry_method,
        launch_recommendation="可作为首发候选" if score >= 7 else "建议先做低成本验证" if score >= 5 else "暂不建议首发",
        recommended_priority=priority,
    )


def _build_global_strategy(markets: list[MarketAnalysis]) -> MarketAnalysis:
    sorted_markets = sorted(markets, key=lambda item: item.launch_fit_score, reverse=True)
    order = " -> ".join(item.market_region for item in sorted_markets)
    avg_score = round(sum(item.launch_fit_score for item in markets) / len(markets))
    return MarketAnalysis(
        market_region="全球化进入策略",
        demand_fit="全球化不是单一结论，应先用分地区实验比较需求强度、转化率和合规成本。",
        willingness_to_pay="建议按地区测试不同价格锚点，避免直接采用统一全球定价。",
        channel_feasibility="先验证线上获客和远程交付，再决定是否进入本地渠道、售后或 B2B 合作。",
        competition_pressure="不同地区替代方案差异较大，需要按地区建立竞品与替代方案清单。",
        compliance_risk="全球化阶段必须建立隐私、数据、AI 使用和硬件认证的地区清单。",
        localization_difficulty="需按语言、销售文案、工作习惯、支付方式和售后预期逐步本地化。",
        launch_fit_score=max(1, min(10, avg_score)),
        advantages=[f"建议进入顺序：{order}", "可用小预算广告和落地页快速比较地区反馈"],
        disadvantages=["跨地区合规和本地化成本容易被低估", "过早全球化会稀释产品定位"],
        key_risks=["地区差异未验证", "统一卖点可能无法跨文化成立", "渠道和售后复杂度上升"],
        recommended_entry_method="先分地区 Landing Page / 广告素材 / 等候名单测试，再确定首发市场。",
        launch_recommendation=f"优先验证 {sorted_markets[0].market_region}",
        recommended_priority="策略项",
    )


def _normalize(text: str) -> str:
    return re.sub(r"\r\n?", "\n", text or "").strip()


def _extract_value(text: str, labels: list[str]) -> str:
    for label in labels:
        pattern = rf"(?:^|\n)\s*(?:#+\s*)?{re.escape(label)}\s*[:：]\s*(.+)"
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" -")
    return ""


def _extract_list(text: str, labels: list[str]) -> list[str]:
    for label in labels:
        section = _extract_section(text, label)
        if section:
            items = re.split(r"\n+|[；;]", section)
            cleaned = [re.sub(r"^\s*[-*0-9.、]+\s*", "", item).strip() for item in items]
            return [item for item in cleaned if item][:6]
    return []


def _extract_section(text: str, label: str) -> str:
    pattern = rf"(?:^|\n)\s*(?:#+\s*)?{re.escape(label)}\s*[:：]?\s*\n?(.+?)(?=\n\s*(?:#+\s*)?\S{{2,20}}\s*[:：]|\Z)"
    match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return match.group(1).strip()


def _infer_positioning(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if len(line.strip()) >= 4), "")
    if first_line:
        return first_line[:160]
    return "输入中未说明，已转化为外部调研问题：一句话定位"


def _infer_target_users(text: str) -> str:
    for keyword in ["用户", "客户", "团队", "企业", "创作者", "开发者", "学生", "办公", "商家", "家长"]:
        if keyword in text:
            return f"输入中提到与“{keyword}”相关的用户线索，但未形成清晰画像；系统将通过市场与竞品调研推测潜在目标客群。"
    return "输入中未明确目标用户，系统将通过市场与竞品调研推测潜在目标客群。"


def _fill_missing_lists(summary: PRDSummary) -> None:
    if not summary.core_features:
        summary.core_features = ["输入中未说明，已转化为外部调研问题：核心功能/MVP 边界"]
    if not summary.use_cases:
        summary.use_cases = ["输入中未说明，已转化为外部调研问题：高频使用场景"]
    if not summary.technical_dependencies:
        summary.technical_dependencies = ["输入中未说明，已转化为外部调研问题：技术与交付依赖"]
    if not summary.potential_risks:
        summary.potential_risks = ["输入中未说明，已转化为外部调研问题：商业、合规与落地风险"]


def _missing_fields(summary: PRDSummary) -> list[str]:
    labels = {
        "product_name": "产品名称",
        "product_positioning": "一句话定位",
        "core_features": "核心功能/MVP 边界",
        "target_users": "目标用户",
        "use_cases": "高频使用场景",
        "business_goals": "商业模式/付费意愿",
        "technical_dependencies": "技术与交付依赖",
        "potential_risks": "风险与合规约束",
    }
    data = asdict(summary)
    fields = []
    for key, value in data.items():
        if key == "missing_information":
            continue
        if _is_unknown(value) or _list_is_unknown(value):
            fields.append(f"{labels.get(key, key)}：输入中未说明，已转化为外部调研问题")
    return fields or ["输入信息较完整，但仍需要外部市场、竞品和真实用户数据验证。"]


def _is_unknown(value: object) -> bool:
    return isinstance(value, str) and (UNKNOWN_RESEARCHED in value or "未说明" in value)


def _list_is_unknown(value: object) -> bool:
    return isinstance(value, list) and any(_is_unknown(item) for item in value)


def _list_preview(values: list[str]) -> str:
    if not values or _list_is_unknown(values):
        return "输入中未说明的场景"
    return "、".join(values[:3])


def _has_search_evidence(agent_outputs: list) -> bool:
    return any(getattr(output, "search_enabled", False) and not getattr(output, "api_error", "") for output in agent_outputs)


def _source_note(agent_outputs: list) -> str:
    if _has_search_evidence(agent_outputs):
        return "用户输入；联网搜索；模型推理"
    return "用户输入；模型推理；搜索结果不足，需人工补充资料"


def _market_advantages(region: str) -> list[str]:
    return {
        "中国市场": ["反馈速度快", "线上渠道和社群测试成本较低", "适合快速迭代卖点"],
        "北美市场": ["订阅和工具付费习惯相对成熟", "适合 Landing Page 和社区冷启动", "众筹和预售机制较成熟"],
        "欧洲市场": ["垂直行业和 B2B 试点机会较多", "用户重视隐私和可信度，有利于可信方案差异化"],
    }[region]


def _market_disadvantages(region: str) -> list[str]:
    return {
        "中国市场": ["竞争反应快", "价格敏感度可能较高", "渠道噪声较大"],
        "北美市场": ["获客成本可能较高", "需要清晰英文定位和证据链", "竞品密度可能较高"],
        "欧洲市场": ["合规复杂度较高", "语言和国家差异更分散", "市场验证周期可能更长"],
    }[region]
