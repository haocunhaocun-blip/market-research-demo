from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


UNKNOWN_RESEARCHED = "输入中未说明，已转化为外部调研问题"


@dataclass
class PRDSummary:
    """Backward-compatible name for the parsed product idea seed."""

    product_name: str = UNKNOWN_RESEARCHED
    product_positioning: str = UNKNOWN_RESEARCHED
    core_features: list[str] = field(default_factory=list)
    target_users: str = UNKNOWN_RESEARCHED
    use_cases: list[str] = field(default_factory=list)
    business_goals: str = UNKNOWN_RESEARCHED
    technical_dependencies: list[str] = field(default_factory=list)
    potential_risks: list[str] = field(default_factory=list)
    missing_information: list[str] = field(default_factory=list)


@dataclass
class AgentOutput:
    topic: str
    agent_name: str
    agent_role: str
    judgment: str
    key_arguments: list[str]
    risks: list[str]
    score: int
    reasoning_basis: list[str]
    model_source: str = "Mock Demo"
    information_source_status: str = "用户输入；模型推理；搜索结果不足，需人工补充资料"
    search_enabled: bool = False
    model_name: str = "Mock Demo"
    search_method: str = "未启用"
    api_error: str = ""


@dataclass
class MarketAnalysis:
    market_region: str
    demand_fit: str
    willingness_to_pay: str
    channel_feasibility: str
    competition_pressure: str
    compliance_risk: str
    localization_difficulty: str
    launch_fit_score: int
    advantages: list[str]
    disadvantages: list[str]
    key_risks: list[str]
    recommended_entry_method: str
    launch_recommendation: str
    recommended_priority: str


@dataclass
class ConsensusReport:
    topic: str
    agent_a_judgment: str
    agent_b_judgment: str
    agent_c_judgment: str
    consensus_points: list[str]
    divergence_points: list[str]
    consensus_level: str
    confidence_score: int
    reasoning_basis: list[str]
    data_source_status: str
    need_validation: bool


@dataclass
class MVPValidationPlan:
    hypothesis_name: str
    hypothesis_content: str
    why_validate: str
    current_basis: str
    related_divergence: str
    risk_level: str
    priority: str
    validation_method: str
    experiment_design: str
    target_sample: str
    success_metric: str
    failure_signal: str
    estimated_cost: str
    estimated_duration: str
    decision_rule: str


@dataclass
class FinalReport:
    prd_summary: PRDSummary
    research_topics: list[str]
    agent_outputs: list[AgentOutput]
    market_analysis: list[MarketAnalysis]
    consensus_report: list[ConsensusReport]
    mvp_validation_plan: list[MVPValidationPlan]
    thirty_day_plan: list[dict[str, str]]
    final_recommendation: str
    markdown_report: str
    product_scores: dict[str, int]


def to_dict_list(items: list[Any]) -> list[dict[str, Any]]:
    return [asdict(item) for item in items]
