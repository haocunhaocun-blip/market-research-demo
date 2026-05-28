from __future__ import annotations

from src.schemas import PRDSummary
from src.schemas import AgentOutput


AGENTS = {
    "Agent A": "市场机会分析师",
    "Agent B": "产品与竞品分析师",
    "Agent C": "红队风险与验证分析师",
}

DATA_SOURCE_STATUS = "用户输入；模型推理；Mock Demo 未联网，搜索结果不足，需人工补充资料"


def run_agent(topic: str, prd_summary: PRDSummary, agent_name: str) -> AgentOutput:
    profile = AGENTS[agent_name]
    text = _summary_text(prd_summary)
    base_score = _base_score(topic, prd_summary)

    if agent_name == "Agent A":
        score = max(1, min(10, base_score - 1))
        judgment = _market_judgment(topic, score)
        arguments = [
            f"市场机会判断应从痛点频率、消费习惯、地区渠道和付费意愿展开。来源类型：模型推理；待验证假设。",
            f"当前用户输入提供的线索是：{text[:100]}。来源类型：用户输入。",
            "Mock Demo 不联网，因此不能声称已获得真实市场趋势数据。来源类型：搜索结果不足，需人工补充资料。",
        ]
        risks = ["缺少真实市场规模数据", "缺少真实用户访谈", "付费意愿和获客成本尚未验证"]
        basis = ["用户输入", "模型推理", "待验证假设", "搜索结果不足，需人工补充资料"]
    elif agent_name == "Agent B":
        score = max(1, min(10, base_score + 1))
        judgment = _product_judgment(topic, score)
        arguments = [
            f"产品体验机会可以先围绕：{_list_preview(prd_summary.core_features)} 收敛 MVP。来源类型：用户输入；模型推理。",
            f"早期功能闭环需要绑定一个高频场景：{_list_preview(prd_summary.use_cases)}。来源类型：用户输入；待验证假设。",
            "需要补充直接竞品、间接竞品和用户当前替代方案清单。来源类型：竞品信息待补充。",
        ]
        risks = ["功能闭环需要原型验证", "用户学习成本可能被低估", "替代方案吸附力未知"]
        basis = ["用户输入", "模型推理", "竞品信息", "待验证假设"]
    else:
        score = max(1, min(10, base_score - 2))
        judgment = _red_team_judgment(topic, score)
        arguments = [
            "如果用户现有替代方案已经足够便宜或顺手，该想法可能是弱需求。来源类型：模型推理；待验证假设。",
            "必须用访谈、评论分析、落地页和预售等行为数据验证，而不是依赖文档完整度。来源类型：模型推理。",
            f"潜在风险线索：{_list_preview(prd_summary.potential_risks)}。来源类型：用户输入。",
        ]
        risks = ["需求频率不足", "用户可能继续使用现有替代方案", "合规和落地成本可能超预期"]
        basis = ["用户输入", "模型推理", "待验证假设"]

    return AgentOutput(
        topic=topic,
        agent_name=agent_name,
        agent_role=profile,
        judgment=judgment,
        key_arguments=arguments,
        risks=risks,
        score=score,
        reasoning_basis=basis,
        model_source="Mock Demo",
        information_source_status=DATA_SOURCE_STATUS,
        model_name="Mock Demo",
        search_method="未启用",
    )


def run_all_agents(topic: str, prd_summary: PRDSummary) -> list[AgentOutput]:
    return [run_agent(topic, prd_summary, agent) for agent in AGENTS]


def _base_score(topic: str, summary: PRDSummary) -> int:
    score = 5
    if "未说明" not in summary.target_users:
        score += 1
    if summary.core_features and "未说明" not in " ".join(summary.core_features):
        score += 1
    if summary.use_cases and "未说明" not in " ".join(summary.use_cases):
        score += 1
    if "付费" in topic or "商业" in topic:
        score -= 1 if "未说明" in summary.business_goals else 0
    if "MVP" in topic or "最小可行版本" in topic:
        score += 1 if summary.core_features else 0
    if "风险" in topic or "验证" in topic:
        score -= 1
    return max(2, min(8, score))


def _market_judgment(topic: str, score: int) -> str:
    if score >= 7:
        return f"{topic}具备一定机会，但必须用外部搜索和低成本实验验证需求强度、地区差异和付费意愿。"
    if score >= 5:
        return f"{topic}存在探索价值，但证据仍偏早期，建议先验证渠道、价格和使用频率。"
    return f"{topic}当前证据偏弱，应先做用户访谈和搜索补证，不宜投入重资源。"


def _product_judgment(topic: str, score: int) -> str:
    if score >= 7:
        return f"{topic}在产品体验和功能闭环上有探索价值，适合先做可点击原型或小范围 Demo。"
    if score >= 5:
        return f"{topic}需要进一步收敛核心路径，避免功能过散导致用户理解成本上升。"
    return f"{topic}的产品闭环尚不清晰，需要重新定义目标用户、触发场景和完成标准。"


def _red_team_judgment(topic: str, score: int) -> str:
    if score >= 6:
        return f"{topic}仍有成立空间，但关键假设不能跳过验证，尤其是替代方案和真实付费。"
    return f"{topic}存在明显不确定性，当前更像逻辑推演，必须进入 MVP 验证路径。"


def _summary_text(summary: PRDSummary) -> str:
    return "；".join(
        [
            summary.product_name,
            summary.product_positioning,
            summary.target_users,
            _list_preview(summary.core_features),
            _list_preview(summary.use_cases),
        ]
    )


def _list_preview(values: list[str]) -> str:
    return "、".join(values[:3]) if values else "输入中未说明，已转化为外部调研问题"
