from __future__ import annotations

from dataclasses import dataclass, field
import re


SOURCE_NOTE = "本地 Demo 模式：基于产品想法与商业逻辑推演，暂无外部数据支撑。"
MISSING_NOTE = "输入中未说明，已转化为市场研究假设"


@dataclass
class IdeaSummary:
    product_name: str
    product_type: str
    raw_idea: str
    one_line_positioning: str
    explicit_information: list[str]
    information_gaps: list[str]


@dataclass
class ScoreItem:
    dimension: str
    score: int
    rationale: str


@dataclass
class OpportunityScorecard:
    items: list[ScoreItem]
    overall_score: int
    opportunity_level: str
    recommended_action: str
    next_three_actions: list[str]


@dataclass
class PainPointAssessment:
    core_pain: str
    pain_intensity: str
    pain_frequency: str
    user_tolerance_cost: str
    must_have_judgment: str
    key_validation_questions: list[str]


@dataclass
class TargetUserSegment:
    segment_type: str
    persona: str
    typical_scenario: str
    purchase_motivation: str
    payment_ability: str
    acquisition_channel: str
    conversion_difficulty: str
    validation_method: str


@dataclass
class MarketSpaceAssessment:
    market_category: str
    trend_direction: str
    growth_drivers: list[str]
    market_ceiling_judgment: str
    niche_to_mass_potential: str
    data_needed: list[str]


@dataclass
class AlternativeAnalysis:
    current_alternatives: list[str]
    alternative_weaknesses: list[str]
    new_product_advantages: list[str]
    switching_resistance: str
    switching_value_score: int
    better_than_existing: str


@dataclass
class CompetitorDifferentiation:
    direct_competitor_types: list[str]
    indirect_competitor_types: list[str]
    competitor_strengths: list[str]
    competitor_weaknesses: list[str]
    differentiation_directions: list[str]
    differentiation_barrier_strength: str
    research_needed: list[str]


@dataclass
class CommercializationAssessment:
    model_fit: str
    pricing_models: list[str]
    willingness_to_pay: str
    purchase_resistance: str
    recommended_path: str
    price_validation_method: str


@dataclass
class ChannelAcquisitionAssessment:
    recommended_channels: list[str]
    channel_priority: list[str]
    marketing_messages: list[str]
    ad_creative_directions: list[str]
    acquisition_difficulties: list[str]
    initial_growth_strategy: str


@dataclass
class RegionMarket:
    region: str
    opportunity: str
    demand_difference: str
    willingness_to_pay: str
    channel_difficulty: str
    compliance_localization_risk: str
    advantages: list[str]
    risks: list[str]
    launch_fit_score: int


@dataclass
class RegionStrategy:
    china: RegionMarket
    north_america: RegionMarket
    europe: RegionMarket
    global_strategy: str
    recommended_first_market: str
    second_priority_market: str
    delayed_market: str
    entry_order: str

    @property
    def regions(self) -> list[RegionMarket]:
        return [self.china, self.north_america, self.europe]


@dataclass
class FeasibilityRiskAssessment:
    technical_risk: str
    supply_chain_risk: str
    cost_risk: str
    after_sales_risk: str
    user_experience_risk: str
    suitable_for_mvp: str
    biggest_obstacle: str


@dataclass
class MVPExperiment:
    hypothesis: str
    validation_method: str
    sample: str
    success_metric: str
    failure_signal: str
    estimated_cost: str
    estimated_duration: str
    decision_rule: str


@dataclass
class MVPValidationPlan:
    experiments: list[MVPExperiment]
    landing_page_test: str
    ad_test: str
    user_interview: str
    survey_test: str
    presale_waitlist_test: str
    thirty_day_plan: list[dict[str, str]]


@dataclass
class MarketResearchReport:
    idea_summary: IdeaSummary
    scorecard: OpportunityScorecard
    pain_point: PainPointAssessment
    target_users: list[TargetUserSegment]
    market_space: MarketSpaceAssessment
    alternative_analysis: AlternativeAnalysis
    competitor_differentiation: CompetitorDifferentiation
    commercialization: CommercializationAssessment
    channel_acquisition: ChannelAcquisitionAssessment
    region_strategy: RegionStrategy
    feasibility_risks: FeasibilityRiskAssessment
    mvp_validation: MVPValidationPlan
    biggest_highlight: str
    biggest_risk: str
    markdown_report: str = field(default="")


def run_market_research_expert(product_name: str, product_type: str, idea_text: str) -> MarketResearchReport:
    summary = parse_idea(product_name, product_type, idea_text)
    pain = _build_pain_point(summary)
    users = _build_target_users(summary)
    market = _build_market_space(summary)
    alternatives = _build_alternatives(summary)
    competitors = _build_competitors(summary)
    commercialization = _build_commercialization(summary)
    channels = _build_channels(summary)
    regions = _build_regions(summary)
    feasibility = _build_feasibility(summary)
    mvp = _build_mvp(summary, regions)
    scorecard = _build_scorecard(summary, pain, market, alternatives, commercialization, channels, feasibility)
    biggest_highlight = _biggest_highlight(scorecard, regions)
    biggest_risk = feasibility.biggest_obstacle

    report = MarketResearchReport(
        idea_summary=summary,
        scorecard=scorecard,
        pain_point=pain,
        target_users=users,
        market_space=market,
        alternative_analysis=alternatives,
        competitor_differentiation=competitors,
        commercialization=commercialization,
        channel_acquisition=channels,
        region_strategy=regions,
        feasibility_risks=feasibility,
        mvp_validation=mvp,
        biggest_highlight=biggest_highlight,
        biggest_risk=biggest_risk,
    )
    report.markdown_report = _build_markdown_report(report)
    return report


def parse_idea(product_name: str, product_type: str, idea_text: str) -> IdeaSummary:
    text = _normalize(idea_text)
    name = product_name.strip() or _extract_value(text, ["产品名称", "项目名称", "名称"]) or f"{MISSING_NOTE}：产品名称"
    positioning = _extract_value(text, ["一句话定位", "产品定位", "定位", "产品想法", "背景"]) or _infer_positioning(text)
    explicit: list[str] = []
    gaps: list[str] = []
    fields = {
        "目标用户": _extract_value(text, ["目标用户", "用户群体", "目标客户", "受众", "客群"]),
        "核心功能": _extract_section(text, ["核心功能", "主要功能", "功能", "解决方案"]),
        "使用场景": _extract_section(text, ["使用场景", "应用场景", "场景", "痛点", "需求"]),
        "商业模式": _extract_value(text, ["商业模式", "收入模式", "定价", "商业化"]),
        "渠道/地区": _extract_value(text, ["渠道", "地区", "市场", "首发市场", "国家"]),
        "风险约束": _extract_section(text, ["风险", "挑战", "限制", "合规"]),
    }
    for label, value in fields.items():
        if value:
            explicit.append(f"{label}：{_compact(value)}")
        elif label == "目标用户":
            gaps.append("目标用户：输入中未明确目标用户，系统将基于产品概念推断潜在目标客群，并将其列为后续验证重点。")
        else:
            gaps.append(f"{label}：{MISSING_NOTE}")
    if not explicit:
        explicit.append(f"产品概念：{_compact(text) or MISSING_NOTE}")
    return IdeaSummary(name, product_type, text, positioning, explicit, gaps)


def _build_pain_point(summary: IdeaSummary) -> PainPointAssessment:
    theme = _theme(summary)
    concrete = _specificity(summary)
    intensity = "高" if concrete >= 3 else "中" if concrete >= 2 else "低"
    frequency = "高频" if summary.product_type in {"AI Agent", "软件产品", "办公效率工具"} else "中频"
    must = "偏 Must-have" if intensity == "高" and frequency == "高频" else "偏 Nice-to-have，需要验证紧迫度"
    return PainPointAssessment(
        core_pain=f"用户在“{theme}”相关任务中可能面临效率低、决策不确定、结果质量不稳定或执行成本高的问题。{SOURCE_NOTE}",
        pain_intensity=intensity,
        pain_frequency=frequency,
        user_tolerance_cost="如果该任务影响收入、成本、交付效率或关键决策，用户忍受成本较高；否则容易停留在兴趣尝试层面。",
        must_have_judgment=must,
        key_validation_questions=[
            "用户过去 30 天是否真实遇到过这个问题？",
            "用户当前为解决该问题花了多少时间、钱或人力？",
            "不用新产品时，用户是否已有可接受替代方案？",
            "用户是否愿意留下联系方式、预约访谈或支付小额预售？",
        ],
    )


def _build_target_users(summary: IdeaSummary) -> list[TargetUserSegment]:
    theme = _theme(summary)
    return [
        TargetUserSegment(
            "核心早期用户",
            f"高频处理“{theme}”任务、对效率或结果质量敏感的个人专业用户/小团队负责人",
            "每天或每周都要完成类似任务，并且当前流程依赖人工经验或多个工具拼接。",
            "希望节省时间、降低试错成本、提升结果稳定性。",
            "中到高，取决于是否能直接带来收入提升或成本节省。",
            "垂直社群、内容 SEO、短视频案例、行业论坛、早期试用名单。",
            "需要证明新方案比现有流程更快、更稳，且迁移成本低。",
            "15-20 个深度访谈 + 可点击原型任务测试。",
        ),
        TargetUserSegment(
            "潜在扩展用户",
            "有预算和流程标准化需求的中小企业、业务团队或运营团队",
            "多人协作、重复交付、结果需要复用或管理者需要可控流程。",
            "希望降本增效、减少返工、形成标准化流程。",
            "较高，但购买链条更长，需要识别使用人、决策人和预算人。",
            "冷邮件、LinkedIn/脉脉、行业社群、案例内容、B2B 小样本试点。",
            "销售周期和信任门槛更高，需要案例、合规和稳定性背书。",
            "5-10 个团队访谈 + 小范围试点意向确认。",
        ),
        TargetUserSegment(
            "暂不优先用户",
            "低频使用、预算弱、只是觉得概念有趣的泛用户",
            "偶尔遇到相关任务，但没有明确损失或强需求。",
            "好奇尝鲜，缺少持续付费动机。",
            "低，容易使用免费工具或手工 workaround。",
            "泛社媒和低成本内容触达即可，不建议早期重投放。",
            "需求不稳定、价格敏感、留存和付费难验证。",
            "用问卷和落地页筛掉低意向用户。",
        ),
    ]


def _build_market_space(summary: IdeaSummary) -> MarketSpaceAssessment:
    category = {
        "AI Agent": "AI 工具 / 垂直智能体 / 生产力软件",
        "软件产品": "SaaS / 工具软件 / 工作流自动化",
        "办公效率工具": "企业效率 / 个人生产力 / 协作工具",
        "硬件产品": "智能硬件 / 消费电子 / 场景化设备",
        "消费电子": "消费电子 / 智能设备 / 生活方式产品",
    }.get(summary.product_type, "待定义的垂直市场")
    return MarketSpaceAssessment(
        market_category=category,
        trend_direction="偏增长，但当前本地 Demo 不引用真实市场规模；需要后续通过 Web Search 补充趋势和规模证据。",
        growth_drivers=["AI 自动化渗透", "垂直场景工具化", "用户对降本增效的持续需求", "线上渠道降低早期验证成本"],
        market_ceiling_judgment="如果只能服务单一低频场景，天花板偏小；如果能从一个高频细分任务扩展到完整工作流，天花板更高。",
        niche_to_mass_potential="建议先切入小众高痛点用户，再通过模板化、渠道化和场景扩展进入更大人群。",
        data_needed=["市场规模和增长率", "目标用户数量和预算区间", "竞品融资/收入/价格信息", "不同地区搜索热度和渠道转化数据"],
    )


def _build_alternatives(summary: IdeaSummary) -> AlternativeAnalysis:
    return AlternativeAnalysis(
        current_alternatives=["手工处理", "通用 AI 工具", "表格/文档/模板", "现有 SaaS 或插件", "外包/咨询/人工助理"],
        alternative_weaknesses=["流程分散", "结果不稳定", "需要用户自己写提示词或搭流程", "缺少垂直场景数据结构", "难以沉淀可复用资产"],
        new_product_advantages=["更聚焦单一高价值场景", "缩短任务路径", "降低使用门槛", "输出更结构化", "便于形成可验证的闭环"],
        switching_resistance="中。若现有流程已经足够便宜顺手，切换阻力会升高；MVP 必须证明明显节省时间或提升结果。",
        switching_value_score=6,
        better_than_existing="具备潜在优势，但必须通过任务流测试证明比现有方案更快、更稳、更省心。",
    )


def _build_competitors(summary: IdeaSummary) -> CompetitorDifferentiation:
    theme = _theme(summary)
    return CompetitorDifferentiation(
        direct_competitor_types=[f"解决“{theme}”的垂直 SaaS/AI 工具", "同类插件、模板、自动化工作流产品", "后续需通过外部搜索补充"],
        indirect_competitor_types=["通用 AI 助手", "办公套件和协作工具", "自动化平台", "人工服务和外包"],
        competitor_strengths=["已有用户习惯", "功能更完整", "品牌或渠道更成熟", "可能已有数据和集成生态"],
        competitor_weaknesses=["泛化导致垂直场景不够深", "上手复杂", "价格或流程不适合早期用户", "本地化或细分需求覆盖不足"],
        differentiation_directions=["更窄目标人群", "更短核心路径", "更低切换成本", "更强本地化", "更明确的结果质量标准"],
        differentiation_barrier_strength="中等偏弱。早期差异化容易被复制，必须通过数据、工作流深度、分发渠道或用户资产增强壁垒。",
        research_needed=["后续需通过外部搜索补充具体竞品名称", "竞品价格页和功能清单", "竞品差评和未满足需求", "竞品渠道和投放策略"],
    )


def _build_commercialization(summary: IdeaSummary) -> CommercializationAssessment:
    if summary.product_type in {"AI Agent", "软件产品", "办公效率工具"}:
        model_fit = "优先 To B2C 或轻 To B：个人可自助试用，小团队可升级团队版。"
        pricing = ["免费试用 + 月订阅", "按量计费", "团队席位", "企业试点费"]
        path = "先做自助试用和等候名单，再验证团队版或企业试点。"
    elif summary.product_type in {"硬件产品", "消费电子"}:
        model_fit = "偏 To C 或 To B2C：需要预售、电商和供应链验证。"
        pricing = ["官网预售", "众筹", "电商单品销售", "硬件 + 服务包"]
        path = "先做视频 Demo、众筹页和小批量预售，再进入量产判断。"
    else:
        model_fit = "商业模式待验证，建议同时测试 To C 自助和 To B 小样本试点。"
        pricing = ["早鸟价", "订阅", "一次性购买", "服务化收费"]
        path = "先通过访谈和价格锚点测试确认谁付费、为什么付费。"
    return CommercializationAssessment(
        model_fit=model_fit,
        pricing_models=pricing,
        willingness_to_pay="中等。若价值能量化为收入提升、成本下降或时间节省，付费意愿会显著提高。",
        purchase_resistance="早期阻力主要来自信任不足、替代方案惯性、预算不明确和结果质量不稳定。",
        recommended_path=path,
        price_validation_method="用价格页 Fake Door、早鸟等候名单、预售/定金和访谈中的预算问题验证。",
    )


def _build_channels(summary: IdeaSummary) -> ChannelAcquisitionAssessment:
    return ChannelAcquisitionAssessment(
        recommended_channels=["垂直社群", "内容 SEO", "短视频/图文案例", "竞品替代关键词", "小预算搜索/社媒广告", "B2B 冷启动访谈"],
        channel_priority=["先做用户访谈和社群验证", "再做 Landing Page + 小预算广告", "最后验证规模化内容或销售渠道"],
        marketing_messages=["节省多少时间", "减少多少试错", "比通用工具更懂该场景", "用一个流程替代多个工具"],
        ad_creative_directions=["痛点前后对比", "30 秒完成任务 Demo", "真实工作流截图", "价格/效率锚点测试"],
        acquisition_difficulties=["目标人群过宽会导致素材无效", "早期缺少案例和信任背书", "广告点击不等于真实需求", "B2B 决策链可能较长"],
        initial_growth_strategy="用窄人群、强痛点、低预算实验获取前 30-50 个高质量反馈，再决定是否扩大渠道。",
    )


def _build_regions(summary: IdeaSummary) -> RegionStrategy:
    base = 6 if summary.product_type in {"AI Agent", "软件产品", "办公效率工具"} else 5
    china = RegionMarket("中国市场", "适合快速验证卖点、社群反馈和价格敏感度。", "反馈快、竞争也快。", "中等，需验证价格敏感度。", "中，内容和私域可先行。", "中，需要本地表达、支付和合规适配。", ["反馈速度快", "内容和私域渠道丰富", "低成本访谈方便"], ["同质化竞争快", "价格敏感", "渠道噪声大"], base)
    na = RegionMarket("北美市场", "适合验证 AI/SaaS/生产力工具的订阅意愿。", "更接受工具订阅和自助试用。", "中高，但需要强价值证明。", "中高，广告和内容成本可能较高。", "中高，需要英文定位、隐私条款和客服。", ["工具付费习惯成熟", "Product Hunt/Reddit 等渠道明确", "利于全球扩散"], ["竞品密度高", "获客成本高", "需要可信证据"], base + 1)
    eu = RegionMarket("欧洲市场", "适合隐私、合规、B2B 和专业场景，但验证周期更长。", "国家差异大，需分市场判断。", "中高，B2B 可能更稳。", "高，语言和国家分散。", "高，GDPR 和本地合规要求更强。", ["重视可信度", "B2B 试点机会", "专业化差异空间"], ["合规复杂", "语言分散", "周期更长"], base - 1)
    ordered = sorted([china, na, eu], key=lambda item: item.launch_fit_score, reverse=True)
    return RegionStrategy(
        china=china,
        north_america=na,
        europe=eu,
        global_strategy="先用同一价值主张做分地区落地页、访谈和小预算广告测试，再根据转化率、访谈质量、付费信号和合规成本决定扩张。",
        recommended_first_market=ordered[0].region,
        second_priority_market=ordered[1].region,
        delayed_market=ordered[2].region,
        entry_order=" -> ".join(item.region for item in ordered),
    )


def _build_feasibility(summary: IdeaSummary) -> FeasibilityRiskAssessment:
    if summary.product_type in {"硬件产品", "消费电子"}:
        supply = "高：需要验证供应链、认证、质检、库存和售后。"
        cost = "高：BOM、开模、物流和售后成本可能显著影响毛利。"
        obstacle = "供应链和成本控制可能是最大落地阻碍。"
    else:
        supply = "低：软件/AI 工具通常无实体供应链，但依赖模型、数据和第三方服务稳定性。"
        cost = "中：主要来自模型调用、云服务、获客、人工支持和迭代成本。"
        obstacle = "稳定高质量输出和低摩擦使用体验可能是最大落地阻碍。"
    return FeasibilityRiskAssessment(
        technical_risk="中：MVP 可先做窄场景，但稳定体验、数据结构和边界处理需要验证。",
        supply_chain_risk=supply,
        cost_risk=cost,
        after_sales_risk="中：早期用户需要教育、支持和反馈闭环，若产品不自解释会增加人工成本。",
        user_experience_risk="中高：如果上手步骤多、结果不可控或价值不直观，用户会回到旧方案。",
        suitable_for_mvp="适合先做 MVP：应避免完整大产品，优先验证一个高频任务闭环。",
        biggest_obstacle=obstacle,
    )


def _build_mvp(summary: IdeaSummary, regions: RegionStrategy) -> MVPValidationPlan:
    theme = _theme(summary)
    experiments = [
        MVPExperiment(f"用户高频遇到“{theme}”问题", "用户访谈 + 问卷预调研", "15-30 个潜在用户", "40% 以上能主动描述同类痛点", "用户只觉得概念有趣但没有近期案例", "低", "3-5 天", "通过则进入落地页测试，否则重定义用户或痛点。"),
        MVPExperiment("新方案明显优于现有替代方案", "可点击原型/视频 Demo 任务测试", "10-15 个高意向用户", "多数用户认为比当前方案更快或更省心", "用户不认为值得切换", "低到中", "1 周", "通过则做等候名单，否则收窄 MVP。"),
        MVPExperiment("用户愿意为结果付费或留下强意向信号", "Landing Page + 等候名单/预售", "300-800 次页面访问", "留资、预约或预售达到预设阈值", "点击有但留资低", "中", "1 周", "通过则继续原型开发，否则调整卖点和定价。"),
        MVPExperiment(f"{regions.recommended_first_market} 更适合作为首发市场", "分地区小预算广告测试", "中国/北美/欧洲各一组页面或素材", "首发候选地区转化率和访谈质量领先", "各地区反馈都弱", "中", "1 周", "通过则锁定首发市场，否则重新选择渠道。"),
    ]
    return MVPValidationPlan(
        experiments=experiments,
        landing_page_test="制作 1 个主落地页和 2-3 个卖点版本，比较访问到留资/预约/等候名单转化。",
        ad_test="用小预算分别测试不同人群、地区和卖点，不以曝光为成功指标，重点看留资和访谈预约。",
        user_interview="围绕最近一次痛点经历、当前替代方案、损失成本、付费预算和切换阻力做半结构化访谈。",
        survey_test="用 8-10 个问题筛选痛点频率、现有方案、预算区间、首发功能和地区差异。",
        presale_waitlist_test="设置早鸟价、等候名单或小额定金，用真实行动验证兴趣强度。",
        thirty_day_plan=[
            {"阶段": "第 1 周", "目标": "验证痛点真实性和核心早期用户", "动作": "访谈、问卷、替代方案收集", "成功指标": "找到明确高频痛点人群", "决策": "继续/收窄用户"},
            {"阶段": "第 2 周", "目标": "验证卖点和差异化", "动作": "Landing Page、视频 Demo、任务流测试", "成功指标": "用户能复述价值并愿意留资", "决策": "优化定位/MVP"},
            {"阶段": "第 3 周", "目标": "验证付费和地区", "动作": "价格锚点、预售、分地区投放", "成功指标": "出现明确首发市场和价格信号", "决策": "锁定首发地区"},
            {"阶段": "第 4 周", "目标": "验证 MVP 闭环", "动作": "可点击原型、小样本试用、反馈迭代", "成功指标": "核心任务可完成且愿意继续试用", "决策": "推进/暂停/转向"},
        ],
    )


def _build_scorecard(
    summary: IdeaSummary,
    pain: PainPointAssessment,
    market: MarketSpaceAssessment,
    alternatives: AlternativeAnalysis,
    commercialization: CommercializationAssessment,
    channels: ChannelAcquisitionAssessment,
    feasibility: FeasibilityRiskAssessment,
) -> OpportunityScorecard:
    user_score = 7 if _specificity(summary) >= 3 else 5
    items = [
        ScoreItem("痛点强度", {"高": 8, "中": 6, "低": 4}[pain.pain_intensity], f"痛点强度判断为{pain.pain_intensity}，仍需访谈验证。"),
        ScoreItem("需求频率", {"高频": 8, "中频": 6, "低频": 4}[pain.pain_frequency], f"当前判断为{pain.pain_frequency}，需要确认真实发生频率。"),
        ScoreItem("目标用户清晰度", user_score, "输入越具体，早期用户越容易收敛；缺失信息已转为验证问题。"),
        ScoreItem("市场增长潜力", 7, "符合工具化、自动化或效率提升趋势，但缺少外部市场数据。"),
        ScoreItem("差异化程度", alternatives.switching_value_score, "差异化需要通过任务效率和结果质量对比证明。"),
        ScoreItem("付费可能性", 6, commercialization.willingness_to_pay),
        ScoreItem("渠道可达性", 6, "存在可测试渠道，但早期需要用低预算验证触达和转化。"),
        ScoreItem("落地可行性", 6, feasibility.suitable_for_mvp),
    ]
    overall = round(sum(item.score for item in items) / len(items))
    level = "高" if overall >= 8 else "中" if overall >= 5 else "低"
    action = "值得推进" if overall >= 8 else "谨慎推进" if overall >= 5 else "暂不建议推进"
    return OpportunityScorecard(
        items=items,
        overall_score=overall,
        opportunity_level=level,
        recommended_action=action,
        next_three_actions=["访谈 15-30 个高痛点用户", "制作 Landing Page 测试留资和卖点", f"在{summary.product_type}首发候选地区做小预算渠道测试"],
    )


def _biggest_highlight(scorecard: OpportunityScorecard, regions: RegionStrategy) -> str:
    best = max(scorecard.items, key=lambda item: item.score)
    return f"{best.dimension}相对更有机会；首发市场可优先验证{regions.recommended_first_market}。"


def _build_markdown_report(report: MarketResearchReport) -> str:
    s = report.idea_summary
    lines = [
        "# 早期产品机会研究报告",
        "",
        "## 1. 产品想法摘要",
        f"- 产品名称：{s.product_name}",
        f"- 产品类型：{s.product_type}",
        f"- 用户已提供的信息：{'; '.join(s.explicit_information)}",
        f"- 当前信息缺口：{'; '.join(s.information_gaps)}",
        "",
        "## 2. 一句话定位",
        s.one_line_positioning,
        "",
        "## 3. 市场机会评分卡",
        *[f"- {item.dimension}：{item.score}/10。{item.rationale}" for item in report.scorecard.items],
        f"- 综合机会评分：{report.scorecard.overall_score}/10",
        f"- 机会等级：{report.scorecard.opportunity_level}",
        f"- 推荐动作：{report.scorecard.recommended_action}",
        f"- 下一步最应该做的 3 件事：{'; '.join(report.scorecard.next_three_actions)}",
        "",
        "## 4. 核心痛点判断",
        f"- 核心痛点：{report.pain_point.core_pain}",
        f"- 痛点强度：{report.pain_point.pain_intensity}",
        f"- 痛点频率：{report.pain_point.pain_frequency}",
        f"- 用户忍受成本：{report.pain_point.user_tolerance_cost}",
        f"- Must-have / Nice-to-have 判断：{report.pain_point.must_have_judgment}",
        f"- 关键验证问题：{'; '.join(report.pain_point.key_validation_questions)}",
        "",
        "## 5. 目标用户判断",
    ]
    for user in report.target_users:
        lines.extend([
            f"### {user.segment_type}",
            f"- 用户画像：{user.persona}",
            f"- 典型场景：{user.typical_scenario}",
            f"- 购买动机：{user.purchase_motivation}",
            f"- 付费能力：{user.payment_ability}",
            f"- 获客渠道：{user.acquisition_channel}",
            f"- 转化难点：{user.conversion_difficulty}",
            f"- 验证方式：{user.validation_method}",
            "",
        ])
    lines.extend([
        "## 6. 市场空间判断",
        f"- 所属市场类别：{report.market_space.market_category}",
        f"- 市场趋势方向：{report.market_space.trend_direction}",
        f"- 增长驱动因素：{'; '.join(report.market_space.growth_drivers)}",
        f"- 市场天花板判断：{report.market_space.market_ceiling_judgment}",
        f"- 小众切入到大众扩展的可能性：{report.market_space.niche_to_mass_potential}",
        f"- 需要外部搜索补充的数据：{'; '.join(report.market_space.data_needed)}",
        "",
        "## 7. 替代方案与切换价值",
        f"- 当前替代方案：{'; '.join(report.alternative_analysis.current_alternatives)}",
        f"- 替代方案缺点：{'; '.join(report.alternative_analysis.alternative_weaknesses)}",
        f"- 新产品优势：{'; '.join(report.alternative_analysis.new_product_advantages)}",
        f"- 用户切换阻力：{report.alternative_analysis.switching_resistance}",
        f"- 切换价值评分：{report.alternative_analysis.switching_value_score}/10",
        f"- 是否具备明显优于现有方案的价值：{report.alternative_analysis.better_than_existing}",
        "",
        "## 8. 竞品与差异化机会",
        f"- 直接竞品类型：{'; '.join(report.competitor_differentiation.direct_competitor_types)}",
        f"- 间接竞品类型：{'; '.join(report.competitor_differentiation.indirect_competitor_types)}",
        f"- 竞品优势：{'; '.join(report.competitor_differentiation.competitor_strengths)}",
        f"- 竞品短板：{'; '.join(report.competitor_differentiation.competitor_weaknesses)}",
        f"- 本产品差异化方向：{'; '.join(report.competitor_differentiation.differentiation_directions)}",
        f"- 差异化壁垒强度：{report.competitor_differentiation.differentiation_barrier_strength}",
        f"- 后续需要联网搜索补充的竞品信息：{'; '.join(report.competitor_differentiation.research_needed)}",
        "",
        "## 9. 商业化可行性",
        f"- To C / To B / To B2C 适配性：{report.commercialization.model_fit}",
        f"- 可能的定价模式：{'; '.join(report.commercialization.pricing_models)}",
        f"- 付费意愿判断：{report.commercialization.willingness_to_pay}",
        f"- 购买阻力：{report.commercialization.purchase_resistance}",
        f"- 推荐商业化路径：{report.commercialization.recommended_path}",
        f"- 推荐价格验证方式：{report.commercialization.price_validation_method}",
        "",
        "## 10. 渠道与获客策略",
        f"- 推荐渠道：{'; '.join(report.channel_acquisition.recommended_channels)}",
        f"- 渠道优先级：{'; '.join(report.channel_acquisition.channel_priority)}",
        f"- 适合的营销卖点：{'; '.join(report.channel_acquisition.marketing_messages)}",
        f"- 广告素材方向：{'; '.join(report.channel_acquisition.ad_creative_directions)}",
        f"- 获客难点：{'; '.join(report.channel_acquisition.acquisition_difficulties)}",
        f"- 初期增长策略：{report.channel_acquisition.initial_growth_strategy}",
        "",
        "## 11. 地区市场进入分析",
    ])
    for region in report.region_strategy.regions:
        lines.extend([
            f"### {region.region}",
            f"- 机会：{region.opportunity}",
            f"- 用户需求差异：{region.demand_difference}",
            f"- 付费意愿：{region.willingness_to_pay}",
            f"- 渠道难度：{region.channel_difficulty}",
            f"- 合规和本地化风险：{region.compliance_localization_risk}",
            f"- 优势：{'; '.join(region.advantages)}",
            f"- 风险：{'; '.join(region.risks)}",
            f"- 首发适配度：{region.launch_fit_score}/10",
            "",
        ])
    lines.extend([
        f"- 全球化进入策略：{report.region_strategy.global_strategy}",
        f"- 最推荐首发市场：{report.region_strategy.recommended_first_market}",
        f"- 第二优先市场：{report.region_strategy.second_priority_market}",
        f"- 暂缓进入市场：{report.region_strategy.delayed_market}",
        f"- 推荐进入顺序：{report.region_strategy.entry_order}",
        "",
        "## 12. 落地可行性与交付风险",
        f"- 技术风险：{report.feasibility_risks.technical_risk}",
        f"- 供应链风险：{report.feasibility_risks.supply_chain_risk}",
        f"- 成本风险：{report.feasibility_risks.cost_risk}",
        f"- 售后风险：{report.feasibility_risks.after_sales_risk}",
        f"- 用户体验风险：{report.feasibility_risks.user_experience_risk}",
        f"- 是否适合先做 MVP：{report.feasibility_risks.suitable_for_mvp}",
        f"- 最大落地阻碍：{report.feasibility_risks.biggest_obstacle}",
        "",
        "## 13. MVP 验证路径",
    ])
    for exp in report.mvp_validation.experiments:
        lines.extend([
            f"### {exp.hypothesis}",
            f"- 验证方法：{exp.validation_method}",
            f"- 样本对象：{exp.sample}",
            f"- 成功指标：{exp.success_metric}",
            f"- 失败信号：{exp.failure_signal}",
            f"- 预计成本：{exp.estimated_cost}",
            f"- 预计周期：{exp.estimated_duration}",
            f"- 下一步决策规则：{exp.decision_rule}",
            "",
        ])
    lines.extend([
        "## 14. 30 天验证计划",
        *[f"- {week['阶段']}：{week['目标']}。动作：{week['动作']}。成功指标：{week['成功指标']}。决策：{week['决策']}。" for week in report.mvp_validation.thirty_day_plan],
        "",
        "## 15. 最终建议",
        f"- {report.scorecard.recommended_action}：综合机会评分 {report.scorecard.overall_score}/10，机会等级 {report.scorecard.opportunity_level}。",
        f"- 最大亮点：{report.biggest_highlight}",
        f"- 最大风险：{report.biggest_risk}",
        "",
        "## 16. 后续需要真实调研补充的数据",
        "- 真实竞品名称、价格、功能差异、评论和用户流失原因。",
        "- 目标用户数量、预算区间、付费转化和渠道成本。",
        "- 中国、北美、欧洲的搜索热度、广告点击、落地页留资和合规要求。",
        "- 真实用户访谈、问卷、预售和等候名单数据。",
        "",
        f"> {SOURCE_NOTE}",
    ])
    return "\n".join(lines)


def _specificity(summary: IdeaSummary) -> int:
    return sum(1 for item in summary.explicit_information if MISSING_NOTE not in item)


def _normalize(text: str) -> str:
    return re.sub(r"\r\n?", "\n", text or "").strip()


def _extract_value(text: str, labels: list[str]) -> str:
    for label in labels:
        match = re.search(rf"(?:^|\n)\s*(?:#+\s*)?{re.escape(label)}\s*[:：]\s*(.+)", text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip(" -")
    return ""


def _extract_section(text: str, labels: list[str]) -> str:
    for label in labels:
        pattern = rf"(?:^|\n)\s*(?:#+\s*)?{re.escape(label)}\s*[:：]?\s*\n?(.+?)(?=\n\s*(?:#+\s*)?\S{{2,20}}\s*[:：]|\Z)"
        match = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


def _infer_positioning(text: str) -> str:
    first_line = next((line.strip() for line in text.splitlines() if len(line.strip()) >= 4), "")
    return first_line[:160] if first_line else f"{MISSING_NOTE}：一句话定位"


def _theme(summary: IdeaSummary) -> str:
    text = re.sub(r"\s+", "", summary.one_line_positioning)
    return text[:28] or "该产品概念"


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()[:180]
