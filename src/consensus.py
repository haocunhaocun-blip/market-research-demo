from __future__ import annotations

from src.schemas import AgentOutput, ConsensusReport


def arbitrate_topic(topic: str, outputs: list[AgentOutput]) -> ConsensusReport:
    by_agent = {item.agent_name: item for item in outputs}
    scores = [item.score for item in outputs]
    spread = max(scores) - min(scores)
    avg_score = sum(scores) / len(scores)

    if spread <= 1:
        level = "高共识"
    elif spread <= 3:
        level = "中等共识"
    else:
        level = "高分歧"

    confidence = max(1, min(10, round(10 - spread - _uncertainty_penalty(outputs))))
    need_validation = level == "高分歧" or confidence <= 6 or _is_validation_topic(topic)

    return ConsensusReport(
        topic=topic,
        agent_a_judgment=by_agent["Agent A"].judgment,
        agent_b_judgment=by_agent["Agent B"].judgment,
        agent_c_judgment=by_agent["Agent C"].judgment,
        consensus_points=_build_consensus_points(topic, avg_score),
        divergence_points=_build_divergence_points(outputs, spread),
        consensus_level=level,
        confidence_score=confidence,
        reasoning_basis=_merge_basis(outputs),
        data_source_status=_merge_source_status(outputs),
        need_validation=need_validation,
    )


def arbitrate_all(agent_outputs: list[AgentOutput]) -> list[ConsensusReport]:
    grouped: dict[str, list[AgentOutput]] = {}
    for output in agent_outputs:
        grouped.setdefault(output.topic, []).append(output)
    return [arbitrate_topic(topic, outputs) for topic, outputs in grouped.items()]


def _build_consensus_points(topic: str, avg_score: float) -> list[str]:
    points = [
        f"三类 Agent 均围绕“{topic}”形成了独立判断。",
        "当前结论不是 PRD 完整性判断，仍需要结合外部资料、真实用户行为和商业转化数据验证。",
    ]
    if avg_score >= 6:
        points.append("整体判断偏正向，但仍需要验证需求强度、使用频率和商业转化。")
    else:
        points.append("整体判断偏谨慎，关键假设需要优先验证。")
    return points


def _build_divergence_points(outputs: list[AgentOutput], spread: int) -> list[str]:
    if spread <= 1:
        return ["三类 Agent 在评分和方向上较接近，主要分歧较小。"]
    sorted_outputs = sorted(outputs, key=lambda item: item.score)
    return [
        f"{sorted_outputs[-1].agent_name} 给出最高分 {sorted_outputs[-1].score}，更关注机会面。",
        f"{sorted_outputs[0].agent_name} 给出最低分 {sorted_outputs[0].score}，更关注风险和证据不足。",
        "分歧主要来自产品体验机会与商业/落地风险之间的权衡。",
    ]


def _merge_basis(outputs: list[AgentOutput]) -> list[str]:
    basis: list[str] = []
    for output in outputs:
        for item in output.reasoning_basis:
            if item not in basis:
                basis.append(item)
    return basis


def _merge_source_status(outputs: list[AgentOutput]) -> str:
    statuses: list[str] = []
    for output in outputs:
        for item in output.information_source_status.split("；"):
            item = item.strip()
            if item and item not in statuses:
                statuses.append(item)
    return "；".join(statuses) if statuses else "用户输入；模型推理；搜索结果不足，需人工补充资料"


def _uncertainty_penalty(outputs: list[AgentOutput]) -> int:
    risk_count = sum(len(item.risks) for item in outputs)
    api_failures = sum(1 for item in outputs if item.api_error)
    return (1 if risk_count >= 8 else 0) + api_failures


def _is_validation_topic(topic: str) -> bool:
    keywords = ["痛点", "付费", "定价", "市场", "闭环", "风险", "验证", "高频"]
    return any(keyword in topic for keyword in keywords)
