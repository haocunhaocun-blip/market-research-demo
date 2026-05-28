from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Literal

from src.aihubmix_client import AIHubMixSearchError, SearchMethod, call_aihubmix_model, extract_json_object
from src.schemas import AgentOutput, PRDSummary


RunMode = Literal["normal", "web_search", "surfing"]

AGENT_ROLES = {
    "Agent A": "市场机会分析师：研究市场趋势、用户需求、商业化潜力和地区进入优先级",
    "Agent B": "产品与竞品分析师：研究竞品、替代方案、差异化空间和 MVP 功能闭环",
    "Agent C": "红队风险与验证分析师：研究失败案例、用户抗拒、合规风险和低成本验证实验",
}

DEFAULT_AGENT_MODELS = {
    "Agent A": "gpt-4o-mini-search-preview",
    "Agent B": "gemini-2.5-pro-search",
    "Agent C": "gemini-3-flash-preview-search",
}

MODEL_ENV_VARS = {
    "Agent A": "AIHUBMIX_AGENT_A_MODEL",
    "Agent B": "AIHUBMIX_AGENT_B_MODEL",
    "Agent C": "AIHUBMIX_AGENT_C_MODEL",
}


def get_agent_models() -> dict[str, str]:
    return {
        agent_name: os.getenv(MODEL_ENV_VARS[agent_name], default_model)
        for agent_name, default_model in DEFAULT_AGENT_MODELS.items()
    }


def run_real_agent(
    topic: str,
    prd_summary: PRDSummary,
    agent_name: str,
    run_mode: RunMode = "normal",
    model_overrides: dict[str, str] | None = None,
) -> AgentOutput:
    role = AGENT_ROLES[agent_name]
    model = (model_overrides or get_agent_models()).get(agent_name, DEFAULT_AGENT_MODELS[agent_name]).strip()
    enable_search = run_mode in {"web_search", "surfing"}
    search_method: SearchMethod = "surfing" if run_mode == "surfing" else "web_search_options" if run_mode == "web_search" else "none"
    information_source_status = _source_status(run_mode)

    try:
        content, request_model = call_aihubmix_model(
            model=model,
            messages=[
                {"role": "system", "content": _system_prompt(agent_name, role, run_mode)},
                {"role": "user", "content": _user_prompt(topic, prd_summary, run_mode)},
            ],
            enable_search=enable_search,
            search_method=search_method,
        )
        payload = extract_json_object(content)
        return _output_from_payload(
            topic=topic,
            agent_name=agent_name,
            role=role,
            model_name=request_model,
            payload=payload,
            information_source_status=information_source_status,
            search_enabled=enable_search,
            search_method=_display_search_method(search_method),
        )
    except Exception as exc:
        error_status = "用户输入；模型推理；搜索失败，需人工补充资料" if enable_search or isinstance(exc, AIHubMixSearchError) else "用户输入；模型推理；暂无外部数据支撑"
        request_model = f"{model}:surfing" if search_method == "surfing" and not model.endswith(":surfing") else model
        return AgentOutput(
            topic=topic,
            agent_name=agent_name,
            agent_role=role,
            judgment="该 Agent 的搜索或模型调用失败，但不能因此判定项目无法评估；当前保留基于产品逻辑的初步判断入口。",
            key_arguments=[
                f"搜索失败原因：{exc}",
                "当前仍可基于用户输入、商业逻辑和其他 Agent 结果做初步机会判断。",
                "需要人工补充：市场趋势、竞品清单、目标用户访谈、价格和渠道验证数据。",
                "建议下一步：先做 Landing Page、用户访谈、竞品评论分析或等候名单测试。",
            ],
            risks=[
                f"失败 Agent：{agent_name}",
                f"使用模型：{request_model}",
                f"搜索方式：{_display_search_method(search_method)}",
                "搜索结果不足，需人工补充资料。",
            ],
            score=4,
            reasoning_basis=["用户输入", "模型推理", "待验证假设", "搜索失败"],
            model_source=_model_source(agent_name, request_model, search_method),
            model_name=request_model,
            information_source_status=error_status,
            search_enabled=enable_search,
            search_method=_display_search_method(search_method),
            api_error=str(exc),
        )


def run_all_real_agents(
    topic: str,
    prd_summary: PRDSummary,
    run_mode: RunMode = "normal",
    model_overrides: dict[str, str] | None = None,
) -> list[AgentOutput]:
    return [
        run_real_agent(topic, prd_summary, agent_name, run_mode=run_mode, model_overrides=model_overrides)
        for agent_name in AGENT_ROLES
    ]


def _system_prompt(agent_name: str, role: str, run_mode: RunMode) -> str:
    if run_mode == "web_search":
        source_rule = "本次已启用 AIHubMix Web Search。不要只基于用户输入推理，用户输入只是初始想法，必须主动结合联网搜索结果进行分析。若搜索没有返回有效来源，明确标注“搜索结果不足，需人工补充资料”。"
    elif run_mode == "surfing":
        source_rule = "本次已启用 AIHubMix :surfing 搜索增强。不要只基于用户输入推理，用户输入只是初始想法，必须主动结合联网搜索结果进行分析。若搜索没有返回有效来源，明确标注“搜索结果不足，需人工补充资料”。"
    else:
        source_rule = "本次未启用联网搜索。必须标注：用户输入；模型推理；暂无外部数据支撑，并提出后续需要搜索或验证的问题。"

    role_task = {
        "Agent A": "重点搜索并分析市场趋势、用户需求、行业增长、消费习惯、付费意愿、商业化潜力和中国/北美/欧洲进入优先级。",
        "Agent B": "重点搜索并分析直接竞品、间接竞品、替代方案、现有产品解决方式、差异化机会、产品功能闭环和 MVP 形态。",
        "Agent C": "重点搜索并分析失败案例、负面评论、用户抗拒点、合规风险、伪需求风险、落地风险，并提出低成本验证实验。",
    }[agent_name]

    return f"""
你是 {agent_name}，角色是：{role}。

你正在参与一个“早期产品机会研究 Agent / Early-stage Product Opportunity Research Agent”。
用户输入可能只是几句话、产品概念、简单 PRD 或完整 PRD。输入不完整是正常情况。

核心规则：
1. {role_task}
2. 如果用户输入缺少信息，请将其视为待研究问题，并通过联网搜索、竞品分析和商业逻辑推演进行补充判断。
3. 不要因为输入不完整而停止分析，不要说“由于 PRD 缺少信息所以无法评估”。
4. 需要区分：用户已提供的信息、联网搜索得到的信息、竞品信息、市场趋势信息、模型推理出的假设、待验证假设。
5. 如果仍然缺乏证据，请提出需要验证的假设和 MVP 实验，而不是直接说无法评估。
6. 不要编造真实市场数据、报告名、链接或具体来源。模型返回了来源摘要时可以概括保留。
7. {source_rule}
8. 输出必须是严格 JSON，不要输出 Markdown。
9. JSON 字段必须包含：judgment, key_arguments, risks, score, reasoning_basis。
10. key_arguments、risks、reasoning_basis 都是字符串数组；每条关键结论都要在文本中标注来源类型。
11. score 是 1-10 的整数。
""".strip()


def _user_prompt(topic: str, prd_summary: PRDSummary, run_mode: RunMode) -> str:
    return json.dumps(
        {
            "research_topic": topic,
            "idea_seed_summary": asdict(prd_summary),
            "run_mode": run_mode,
            "instruction": "把用户输入当作研究种子，围绕产品机会、市场潜力、目标客群、地区选择、竞品替代、商业化和 MVP 验证输出可执行判断。",
            "source_type_requirements": ["用户输入", "联网搜索", "竞品信息", "市场趋势信息", "模型推理", "待验证假设"],
            "output_language": "zh-CN",
        },
        ensure_ascii=False,
    )


def _output_from_payload(
    topic: str,
    agent_name: str,
    role: str,
    model_name: str,
    payload: dict[str, Any],
    information_source_status: str,
    search_enabled: bool,
    search_method: str,
) -> AgentOutput:
    basis = _as_string_list(payload.get("reasoning_basis"), ["用户输入", "模型推理", "待验证假设"])
    if information_source_status not in basis:
        basis.append(information_source_status)

    return AgentOutput(
        topic=topic,
        agent_name=agent_name,
        agent_role=role,
        judgment=str(payload.get("judgment") or "AI 返回结果中未提供明确结论。"),
        key_arguments=_as_string_list(payload.get("key_arguments"), ["AI 返回结果中未提供关键依据。"]),
        risks=_as_string_list(payload.get("risks"), ["AI 返回结果中未提供风险提示。"]),
        score=_clamp_score(payload.get("score")),
        reasoning_basis=basis,
        model_source=_model_source(agent_name, model_name, _internal_search_method(search_method)),
        model_name=model_name,
        information_source_status=information_source_status,
        search_enabled=search_enabled,
        search_method=search_method,
    )


def _model_source(agent_name: str, model: str, search_method: SearchMethod | str) -> str:
    provider = {
        "Agent A": "OpenAI/GPT via AIHubMix",
        "Agent B": "Gemini via AIHubMix",
        "Agent C": "Gemini via AIHubMix",
    }[agent_name]
    suffix = ""
    if search_method == "web_search_options":
        suffix = " + Web Search"
    elif search_method == "surfing":
        suffix = " + :surfing"
    return f"{provider} / {model}{suffix}"


def _source_status(run_mode: RunMode) -> str:
    if run_mode == "web_search":
        return "用户输入；联网搜索；竞品信息；市场趋势信息；模型推理；待验证假设"
    if run_mode == "surfing":
        return "用户输入；联网搜索；竞品信息；市场趋势信息；模型推理；待验证假设"
    return "用户输入；模型推理；暂无外部数据支撑"


def _display_search_method(search_method: SearchMethod) -> str:
    return {
        "none": "未启用",
        "web_search_options": "web_search_options",
        "surfing": ":surfing",
    }[search_method]


def _internal_search_method(search_method: str) -> SearchMethod:
    if search_method == ":surfing":
        return "surfing"
    if search_method == "web_search_options":
        return "web_search_options"
    return "none"


def _as_string_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or fallback
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return fallback


def _clamp_score(value: Any) -> int:
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        score = 5
    return max(1, min(10, score))
