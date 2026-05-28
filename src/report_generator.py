from __future__ import annotations

from src.schemas import AgentOutput, ConsensusReport, MVPValidationPlan, MarketAnalysis, PRDSummary


def build_mvp_validation_plan(
    consensus_reports: list[ConsensusReport], market_analysis: list[MarketAnalysis]
) -> list[MVPValidationPlan]:
    plans: list[MVPValidationPlan] = []
    for report in consensus_reports:
        if not report.need_validation:
            continue
        method = _match_validation_method(report.topic)
        plans.append(
            MVPValidationPlan(
                hypothesis_name=f"{report.topic}关键假设",
                hypothesis_content=f"如果“{report.topic}”成立，该产品才值得继续投入下一阶段资源。",
                why_validate="该结论存在分歧、低置信度、外部证据不足或仍属于待验证假设。",
                current_basis="；".join(report.reasoning_basis),
                related_divergence="；".join(report.divergence_points),
                risk_level="高" if report.consensus_level == "高分歧" else "中",
                priority="P0" if report.consensus_level == "高分歧" or report.confidence_score <= 5 else "P1",
                validation_method=method,
                experiment_design=_experiment_design(method),
                target_sample=_target_sample(report.topic),
                success_metric=_success_metric(report.topic),
                failure_signal=_failure_signal(report.topic),
                estimated_cost="低" if "访谈" in method or "评论" in method else "中",
                estimated_duration="3 天" if report.confidence_score <= 5 else "1 周",
                decision_rule="达到成功指标则进入原型/转化测试；低于失败信号则收缩定位或暂停推进。",
            )
        )

    if not any("首发" in plan.hypothesis_name or "市场" in plan.hypothesis_name for plan in plans):
        market_candidates = [item for item in market_analysis if item.market_region != "全球化进入策略"]
        best_market = max(market_candidates, key=lambda item: item.launch_fit_score)
        plans.append(
            MVPValidationPlan(
                hypothesis_name="首发市场选择假设",
                hypothesis_content=f"{best_market.market_region}可能更适合作为首发市场。",
                why_validate="市场进入顺序会影响获客成本、转化率和本地化投入。",
                current_basis="用户输入；联网搜索或模型推理；待验证假设。",
                related_divergence="不同地区需求、渠道、付费意愿和合规成本尚未通过真实投放比较。",
                risk_level="中",
                priority="P1",
                validation_method="分地区广告投放测试、不同国家/地区落地页转化率对比",
                experiment_design="用同一产品卖点建立分地区落地页，投放小预算广告，比较点击率、留资率和访谈预约率。",
                target_sample="每个地区至少 100-300 次有效访问或 10-20 个目标用户反馈。",
                success_metric="目标地区留资率明显高于其他地区，且访谈反馈中的痛点强度更高。",
                failure_signal="各地区转化均低或反馈无法证明高频痛点。",
                estimated_cost="中",
                estimated_duration="1 周",
                decision_rule="选择转化率和访谈质量最高的地区作为首发候选。",
            )
        )

    return plans[:10]


def build_thirty_day_plan() -> list[dict[str, str]]:
    return [
        {
            "阶段": "第 1 周：验证核心痛点与目标用户",
            "需要验证的问题": "痛点是否真实、目标用户是谁、场景是否高频。",
            "推荐方法": "用户访谈、问卷预调研、社媒/电商/应用商店评论分析。",
            "样本对象": "15-30 个潜在用户或购买决策人。",
            "成功指标": "超过 40% 受访者主动描述相同痛点，并愿意继续了解方案。",
            "产出物": "目标用户画像、痛点证据表、场景频率判断。",
        },
        {
            "阶段": "第 2 周：验证卖点与转化率",
            "需要验证的问题": "哪个价值主张最能触发用户兴趣。",
            "推荐方法": "不同卖点 Landing Page、Fake Door Test 或广告素材 A/B 测试。",
            "样本对象": "不同目标用户群体的冷启动流量。",
            "成功指标": "出现明确领先卖点，点击率和留资率达到预设阈值。",
            "产出物": "卖点排序、转化漏斗、失败信号记录。",
        },
        {
            "阶段": "第 3 周：验证价格与首发地区",
            "需要验证的问题": "用户是否愿意付费，哪个地区更适合首发。",
            "推荐方法": "价格锚点测试、预售/定金测试、分地区广告投放测试。",
            "样本对象": "中国、北美、欧洲的目标用户样本。",
            "成功指标": "至少一个地区形成更高留资/预售/访谈转化。",
            "产出物": "价格接受区间、地区优先级、首发市场判断。",
        },
        {
            "阶段": "第 4 周：验证 MVP 功能闭环",
            "需要验证的问题": "用户能否理解价值并完成核心任务。",
            "推荐方法": "可点击原型测试、视频 Demo 测试、8 小时工作流观察。",
            "样本对象": "高意向用户和早期种子用户。",
            "成功指标": "多数用户能独立完成核心任务，并愿意进入等候名单或试用。",
            "产出物": "MVP 功能边界、首发市场建议、下一阶段决策。",
        },
    ]


def build_product_scores(consensus_reports: list[ConsensusReport], market_analysis: list[MarketAnalysis]) -> dict[str, int]:
    topic_scores = {report.topic: report.confidence_score for report in consensus_reports}
    market_scores = [item.launch_fit_score for item in market_analysis if item.market_region != "全球化进入策略"]
    avg_market = round(sum(market_scores) / len(market_scores)) if market_scores else 5
    return {
        "市场机会": avg_market,
        "痛点真实性": _score_from_topic(topic_scores, "痛点", 6),
        "目标客群清晰度": _score_from_topic(topic_scores, "用户", 5),
        "竞品差异化": _score_from_topic(topic_scores, "差异化", 5),
        "商业化潜力": _score_from_topic(topic_scores, "付费", 5),
        "MVP 可验证性": _score_from_topic(topic_scores, "MVP", 6),
        "综合推进价值": 0,
    }


def decide_final_recommendation(scores: dict[str, int], consensus_reports: list[ConsensusReport]) -> str:
    working = {key: value for key, value in scores.items() if key != "综合推进价值"}
    overall = round(sum(working.values()) / len(working))
    scores["综合推进价值"] = overall
    high_divergence = sum(1 for item in consensus_reports if item.consensus_level == "高分歧")
    if overall >= 7 and high_divergence <= 2:
        return "值得推进，但先做 30 天低成本验证"
    if overall >= 5:
        return "谨慎推进，必须先验证关键假设"
    return "暂不建议推进，先补充需求和市场证据"


def build_markdown_report(
    prd_summary: PRDSummary,
    research_topics: list[str],
    consensus_report: list[ConsensusReport],
    agent_outputs: list[AgentOutput],
    market_analysis: list[MarketAnalysis],
    mvp_validation_plan: list[MVPValidationPlan],
    thirty_day_plan: list[dict[str, str]],
    product_scores: dict[str, int],
    final_recommendation: str,
) -> str:
    target_segments = _target_segments(prd_summary)
    competitors = _topic_outputs(agent_outputs, ["竞品", "替代方案"])
    market_outputs = _topic_outputs(agent_outputs, ["市场趋势", "中国", "北美", "欧洲", "首发"])

    lines = [
        "# 早期产品机会研究报告",
        "",
        "## 1. 产品想法摘要",
        f"- 用户输入的核心想法：{prd_summary.product_positioning}（来源类型：用户输入）",
        f"- 系统理解的一句话定位：面向潜在目标用户，围绕“{prd_summary.product_positioning}”探索可商业化解决方案。（来源类型：模型推理）",
        f"- 当前信息缺口：{'; '.join(prd_summary.missing_information)}",
        "",
        "## 2. 外部市场研究摘要",
        f"- 市场趋势：{_first_judgment(market_outputs, '市场趋势仍需通过联网搜索和人工资料补充。')}（来源类型：联网搜索/市场趋势信息/模型推理）",
        f"- 用户需求信号：围绕痛点真实性、目标用户和替代方案的多 Agent 判断见下方共识。（来源类型：用户输入；模型推理；待验证假设）",
        f"- 竞品和替代方案：{_first_judgment(competitors, '需要补充直接竞品、间接竞品和用户当前替代方案。')}（来源类型：竞品信息；联网搜索；待验证假设）",
        f"- 地区市场机会：{_market_order(market_analysis)}（来源类型：模型推理；待验证假设）",
        "",
        "## 3. 目标客群推断",
    ]
    for segment in target_segments:
        lines.extend(
            [
                f"### {segment['name']}",
                f"- 痛点：{segment['pain']}",
                f"- 当前替代方案：{segment['alternative']}",
                f"- 付费可能性：{segment['payment']}",
                f"- 获客渠道建议：{segment['channel']}",
                "",
            ]
        )

    lines.append("## 4. 多地区市场分析")
    for market in market_analysis:
        lines.extend(
            [
                f"### {market.market_region}",
                f"- 需求匹配度：{market.demand_fit}",
                f"- 付费意愿：{market.willingness_to_pay}",
                f"- 渠道策略：{market.channel_feasibility}",
                f"- 合规风险：{market.compliance_risk}",
                f"- 首发适配度：{market.launch_fit_score}/10",
                f"- 进入建议：{market.launch_recommendation}",
                "",
            ]
        )

    lines.extend(
        [
            "## 5. 竞品与替代方案分析",
            "- 直接竞品：需要通过联网搜索建立候选清单，不得在无来源时编造具体品牌。（来源类型：竞品信息；待验证假设）",
            "- 间接竞品：包括人工流程、通用工具、表格/文档、咨询服务、社区方案或用户自建流程。（来源类型：模型推理）",
            "- 用户当前替代方案：应优先从竞品评论、社群讨论和用户访谈中提取。（来源类型：联网搜索；待验证假设）",
            "- 差异化机会：更窄目标用户、更短任务路径、更低切换成本、更可信的结果或更适合首发地区的渠道。（来源类型：模型推理）",
            "",
            "## 6. 商业化判断",
            f"- To C / To B / To B2C 适配性：{_first_consensus(consensus_report, 'To C', '需要围绕用户、购买决策人和付费场景继续验证。')}",
            "- 定价方向：先测试价格锚点，不直接假设用户愿意按完整版本付费。（来源类型：待验证假设）",
            "- 渠道策略：按地区测试官网、内容、电商、众筹、垂直社区或 B2B 销售。（来源类型：模型推理）",
            "- 众筹 / 官网 / 电商 / B2B 销售适配性：根据产品交付形态和首发地区决定，不在证据不足时提前锁死。（来源类型：模型推理；待验证假设）",
            "",
            "## 7. 多 Agent 共识与分歧",
        ]
    )
    for item in consensus_report:
        topic_outputs = [output for output in agent_outputs if output.topic == item.topic]
        lines.append(f"### {item.topic}")
        for output in topic_outputs:
            lines.extend(
                [
                    f"- {output.agent_name} 的判断：{output.judgment}",
                    f"  - 来源状态：{output.information_source_status}",
                ]
            )
            if output.api_error:
                lines.append(f"  - 搜索/调用失败原因：{output.api_error}")
        lines.extend(
            [
                f"- 共识点：{'; '.join(item.consensus_points)}",
                f"- 分歧点：{'; '.join(item.divergence_points)}",
                f"- 信息来源差异：{item.data_source_status}",
                f"- 需要人工核查的信息：{'是' if item.need_validation else '暂不优先'}",
                "",
            ]
        )

    lines.append("## 8. MVP 验证路径")
    for plan in mvp_validation_plan:
        lines.extend(
            [
                f"### {plan.hypothesis_name}",
                f"- 关键假设：{plan.hypothesis_content}",
                f"- 验证方法：{plan.validation_method}",
                f"- Landing Page 测试：可用于验证卖点、首发地区和留资率。",
                f"- 广告买量测试：用小预算比较不同用户群和地区。",
                f"- 用户访谈：验证痛点频率、替代方案和支付意愿。",
                f"- 竞品评论分析：提取负面评论、未满足需求和切换阻力。",
                f"- 预售 / 等候名单测试：验证真实行动意愿。",
                f"- 最小实验：{plan.experiment_design}",
                "",
            ]
        )
    lines.append("### 30 天验证计划")
    for week in thirty_day_plan:
        lines.extend([f"- {week['阶段']}：{week['推荐方法']} 成功指标：{week['成功指标']}"])

    lines.extend(
        [
            "",
            "## 9. 最终建议",
            f"- 结论：{final_recommendation}",
            f"- 推荐首发市场：{_recommended_market(market_analysis)}",
            f"- 推荐目标客群：{target_segments[0]['name']}",
            "- 推荐 MVP 版本：围绕单一高频痛点做最短可验证任务闭环。",
            "- 下一步最应该做的 3 件事：用户访谈；竞品/替代方案评论分析；分地区 Landing Page 或等候名单测试。",
            "",
            "## 产品综合评分",
            *[f"- {key}：{value}/10" for key, value in product_scores.items()],
            "",
            "> 来源说明：关键结论应标注用户输入、联网搜索、竞品信息、市场趋势信息、模型推理或待验证假设。若启用联网搜索但未返回有效来源，应标注“搜索结果不足，需人工补充资料”。",
        ]
    )
    return "\n".join(lines)


def _match_validation_method(topic: str) -> str:
    if "痛点" in topic:
        return "用户访谈、问卷预调研、社媒评论与私信反馈分析"
    if "付费" in topic or "定价" in topic or "商业" in topic:
        return "Landing Page 买量测试、预售/定金测试、价格 A/B 测试"
    if "市场" in topic or "地区" in topic:
        return "分地区广告投放测试、不同国家/地区落地页转化率对比"
    if "竞品" in topic or "替代" in topic:
        return "竞品评论分析、替代流程访谈、切换成本测试"
    if "MVP" in topic or "最小可行" in topic:
        return "可点击原型测试、视频 Demo 测试、任务流测试"
    return "用户访谈、可点击原型测试、Fake Door Test 假门测试"


def _experiment_design(method: str) -> str:
    return f"围绕核心机会假设设计最小实验，使用 {method} 收集行为数据和定性反馈。"


def _target_sample(topic: str) -> str:
    if "市场" in topic or "地区" in topic:
        return "每个候选地区 100-300 次有效访问或 10-20 个目标用户反馈。"
    return "15-30 个目标用户，优先选择高频场景用户和潜在付费用户。"


def _success_metric(topic: str) -> str:
    if "付费" in topic or "定价" in topic:
        return "出现明确价格接受区间，留资、预售或定金转化达到预设阈值。"
    if "痛点" in topic:
        return "超过 40% 受访者能主动描述相同痛点，并愿意继续试用或留资。"
    return "用户能理解价值主张，并完成核心任务或表达明确试用意愿。"


def _failure_signal(topic: str) -> str:
    return "用户无法复述核心价值、反馈痛点不高频，或不愿为现有方案切换成本买单。"


def _score_from_topic(topic_scores: dict[str, int], keyword: str, fallback: int) -> int:
    for topic, score in topic_scores.items():
        if keyword in topic:
            return score
    return fallback


def _topic_outputs(outputs: list[AgentOutput], keywords: list[str]) -> list[AgentOutput]:
    return [output for output in outputs if any(keyword in output.topic for keyword in keywords)]


def _first_judgment(outputs: list[AgentOutput], fallback: str) -> str:
    return outputs[0].judgment if outputs else fallback


def _first_consensus(reports: list[ConsensusReport], keyword: str, fallback: str) -> str:
    for report in reports:
        if keyword in report.topic:
            return "；".join(report.consensus_points)
    return fallback


def _market_order(markets: list[MarketAnalysis]) -> str:
    candidates = [item for item in markets if item.market_region != "全球化进入策略"]
    ordered = sorted(candidates, key=lambda item: item.launch_fit_score, reverse=True)
    return " > ".join(f"{item.market_region}({item.launch_fit_score}/10)" for item in ordered)


def _recommended_market(markets: list[MarketAnalysis]) -> str:
    candidates = [item for item in markets if item.market_region != "全球化进入策略"]
    return max(candidates, key=lambda item: item.launch_fit_score).market_region if candidates else "待验证"


def _target_segments(summary: PRDSummary) -> list[dict[str, str]]:
    base_user = summary.target_users if "未说明" not in summary.target_users else "高频遇到该痛点的早期尝鲜用户"
    return [
        {
            "name": base_user,
            "pain": "需要更快、更低成本或更可信地完成当前任务。（来源类型：用户输入；模型推理）",
            "alternative": "现有工具、人工流程、通用软件或竞品方案。（来源类型：竞品信息；待验证假设）",
            "payment": "如果痛点高频且能节省时间/成本，则具备付费可能。（来源类型：模型推理；待验证假设）",
            "channel": "垂直社区、内容搜索、私域访谈、应用商店/电商评论反向触达。",
        },
        {
            "name": "有明确预算或采购权的小团队/企业用户",
            "pain": "需要稳定、可管理、可复用的流程改进。（来源类型：模型推理）",
            "alternative": "内部流程、外包服务、SaaS 套件或人工协作。（来源类型：待验证假设）",
            "payment": "若能证明降本增效，付费可能性高于泛 To C 用户。",
            "channel": "行业社群、LinkedIn/脉脉、冷邮件、案例型内容和小样本试点。",
        },
        {
            "name": "对现有方案不满的竞品用户",
            "pain": "现有产品过贵、过复杂、不本地化或无法覆盖特定场景。（来源类型：竞品信息；待验证假设）",
            "alternative": "直接竞品、插件、模板、人工 workaround。",
            "payment": "取决于迁移成本和差异化强度，需要价格页/预售测试。",
            "channel": "竞品评论区、替代方案关键词搜索、垂直论坛和比较页 SEO。",
        },
    ]
