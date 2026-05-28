from __future__ import annotations

from html import escape

import pandas as pd
import plotly.express as px
import streamlit as st

from src.schemas import AgentOutput, ConsensusReport, FinalReport, MVPValidationPlan, MarketAnalysis


def inject_app_styles() -> None:
    st.markdown(
        """
<style>
  :root {
    --panel-bg: #ffffff;
    --soft-bg: #f7f9fc;
    --line: #dde5f0;
    --text-soft: #5f6b7a;
    --agent-a: #2f6fed;
    --agent-b: #00a389;
    --agent-c: #d85b43;
    --summary: #27364f;
  }

  .block-container { padding-top: 2rem; }

  .agent-page-hero {
    border: 1px solid var(--line);
    background: linear-gradient(135deg, #f8fbff 0%, #eef5ff 100%);
    border-radius: 8px;
    padding: 18px 20px;
    margin: 4px 0 22px 0;
  }

  .agent-page-hero h3 {
    margin: 0 0 6px 0;
    font-size: 1.05rem;
    color: #182235;
  }

  .agent-page-hero p {
    margin: 0;
    color: var(--text-soft);
    line-height: 1.6;
  }

  .topic-section {
    padding: 8px 0 24px 0;
    margin: 8px 0 30px 0;
    border-top: 1px solid var(--line);
  }

  .topic-heading {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin: 14px 0 14px 0;
  }

  .topic-heading h3 {
    margin: 0;
    color: #141c2b;
    font-size: 1.25rem;
    letter-spacing: 0;
  }

  .topic-index {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 34px;
    height: 26px;
    border-radius: 8px;
    background: #eef3fb;
    color: #40526d;
    font-size: 0.78rem;
    font-weight: 700;
  }

  .agent-card,
  .summary-card,
  .market-card,
  .validation-card,
  .week-card {
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel-bg);
    padding: 16px;
    box-shadow: 0 8px 22px rgba(16, 24, 40, 0.06);
  }

  .agent-card {
    min-height: 360px;
    border-top: 4px solid #64748b;
  }

  .agent-a { border-top-color: var(--agent-a); }
  .agent-b { border-top-color: var(--agent-b); }
  .agent-c { border-top-color: var(--agent-c); }

  .agent-meta,
  .card-meta {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 12px;
  }

  .agent-name,
  .card-title {
    font-weight: 800;
    color: #111827;
    font-size: 1.02rem;
  }

  .agent-role,
  .card-subtitle {
    color: var(--text-soft);
    font-size: 0.84rem;
    line-height: 1.45;
    margin-top: 3px;
  }

  .score-badge,
  .level-badge {
    display: inline-flex;
    white-space: nowrap;
    align-items: center;
    border-radius: 8px;
    padding: 4px 8px;
    font-size: 0.78rem;
    font-weight: 700;
    color: #172033;
    background: #eef3fb;
  }

  .judgment {
    color: #141c2b;
    font-weight: 750;
    line-height: 1.55;
    font-size: 1.02rem;
    margin: 12px 0 14px 0;
  }

  .card-label {
    color: #334155;
    font-size: 0.82rem;
    font-weight: 750;
    margin: 12px 0 6px 0;
  }

  .agent-card ul,
  .summary-card ul,
  .market-card ul,
  .validation-card ul,
  .week-card ul {
    margin: 0;
    padding-left: 18px;
    color: #334155;
    line-height: 1.48;
    font-size: 0.9rem;
  }

  .risk-box {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 8px;
    padding: 10px 12px;
    margin-top: 12px;
    color: #7c2d12;
    font-size: 0.88rem;
    line-height: 1.5;
  }

  .progress-track {
    height: 7px;
    border-radius: 999px;
    background: #e8edf5;
    overflow: hidden;
    margin-top: 8px;
  }

  .progress-fill {
    height: 7px;
    border-radius: 999px;
    background: linear-gradient(90deg, #2f6fed, #00a389);
  }

  .summary-card {
    min-height: auto;
    background: linear-gradient(135deg, #172033 0%, #243756 100%);
    color: #f8fafc;
    border-color: #31476c;
    margin-top: 12px;
  }

  .summary-card h4 {
    margin: 0 0 10px 0;
    color: #ffffff;
    font-size: 1.04rem;
  }

  .summary-grid,
  .market-grid,
  .validation-grid,
  .week-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
  }

  .summary-card ul,
  .summary-card .card-label { color: #dbe7ff; }

  .summary-line {
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 12px;
    margin-top: 12px;
    color: #f8fafc;
    line-height: 1.55;
  }

  .summary-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    margin: 10px 0 6px 0;
  }

  .summary-meta .level-badge {
    color: #f8fafc;
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.16);
  }

  .market-card {
    min-height: 520px;
    border-top: 4px solid #2f6fed;
    margin-bottom: 16px;
  }

  .market-card.strategy {
    border-top-color: #7c3aed;
    background: linear-gradient(135deg, #ffffff 0%, #f7f3ff 100%);
  }

  .market-score {
    font-size: 1.75rem;
    font-weight: 850;
    color: #172033;
    line-height: 1;
    text-align: right;
  }

  .market-score span {
    display: block;
    color: var(--text-soft);
    font-size: 0.76rem;
    font-weight: 700;
    margin-top: 5px;
  }

  .insight-box {
    background: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 10px 12px;
    margin-top: 10px;
    color: #263449;
    font-size: 0.9rem;
    line-height: 1.52;
  }

  .tag-row {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin: 8px 0 10px 0;
  }

  .soft-tag {
    border-radius: 8px;
    padding: 4px 8px;
    font-size: 0.76rem;
    font-weight: 750;
    color: #24344d;
    background: #eef3fb;
  }

  .validation-card {
    min-height: 560px;
    border-top: 4px solid #00a389;
    margin-bottom: 16px;
  }

  .validation-card.priority-p0 { border-top-color: #d85b43; }
  .validation-card.priority-p1 { border-top-color: #f59e0b; }

  .hypothesis {
    color: #111827;
    font-size: 1rem;
    font-weight: 760;
    line-height: 1.5;
    margin: 10px 0;
  }

  .decision-box {
    background: #eef8f5;
    border: 1px solid #bfe5dc;
    border-radius: 8px;
    padding: 10px 12px;
    color: #10483e;
    line-height: 1.5;
    margin-top: 12px;
  }

  .week-card {
    min-height: 330px;
    border-top: 4px solid #27364f;
    margin-bottom: 16px;
  }

  @media (max-width: 900px) {
    .summary-grid,
    .market-grid,
    .validation-grid,
    .week-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
        """,
        unsafe_allow_html=True,
    )


def render_score_board(report: FinalReport) -> None:
    st.subheader("产品综合评分看板")
    columns = st.columns(4)
    for index, (name, score) in enumerate(report.product_scores.items()):
        columns[index % 4].metric(name, f"{score}/10")

    chart_data = pd.DataFrame(
        [{"维度": key, "评分": value} for key, value in report.product_scores.items()]
    )
    st.plotly_chart(
        px.bar(chart_data, x="维度", y="评分", range_y=[0, 10], text="评分"),
        use_container_width=True,
    )


def render_agent_analysis(report: FinalReport) -> None:
    st.markdown(
        """
<div class="agent-page-hero">
  <h3>子 Agent 独立分析</h3>
  <p>系统把用户输入当作研究种子，并由 3 个独立子 Agent 分别分析市场机会、产品竞品和红队风险，最后生成共识总结。</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    consensus_by_topic = {item.topic: item for item in report.consensus_report}
    outputs_by_topic: dict[str, list[AgentOutput]] = {}
    for output in report.agent_outputs:
        outputs_by_topic.setdefault(output.topic, []).append(output)

    for index, topic in enumerate(report.research_topics, start=1):
        outputs = outputs_by_topic.get(topic, [])
        consensus = consensus_by_topic.get(topic)
        if not outputs or consensus is None:
            continue
        render_topic_section(index, topic, outputs, consensus)


def render_topic_section(index: int, topic: str, outputs: list[AgentOutput], consensus: ConsensusReport) -> None:
    st.markdown(
        f"""
<section class="topic-section">
  <div class="topic-heading">
    <h3>{escape(topic)}</h3>
    <span class="topic-index">#{index:02d}</span>
  </div>
</section>
        """,
        unsafe_allow_html=True,
    )

    columns = st.columns(3)
    for column, output in zip(columns, outputs):
        with column:
            render_agent_card(output)

    render_summary_card(consensus)


def render_agent_card(output: AgentOutput) -> None:
    class_name = {
        "Agent A": "agent-a",
        "Agent B": "agent-b",
        "Agent C": "agent-c",
    }.get(output.agent_name, "")
    api_error_html = ""
    if output.api_error:
        api_error_html = f"""
  <div class="risk-box">
    <strong>API 调用错误</strong><br>{escape(output.api_error)}
  </div>
"""
    st.markdown(
        f"""
<div class="agent-card {class_name}">
  <div class="agent-meta">
    <div>
      <div class="agent-name">{escape(output.agent_name)}</div>
      <div class="agent-role">{escape(output.agent_role)}</div>
    </div>
    <span class="score-badge">{output.score}/10</span>
  </div>
  <div class="tag-row">
    <span class="soft-tag">模型来源：{escape(output.model_source)}</span>
    <span class="soft-tag">使用模型：{escape(output.model_name)}</span>
    <span class="soft-tag">联网搜索：{'已启用' if output.search_enabled else '未启用'}</span>
    <span class="soft-tag">搜索方式：{escape(output.search_method)}</span>
    <span class="soft-tag">信息来源：{escape(output.information_source_status)}</span>
  </div>
  <div class="progress-track"><div class="progress-fill" style="width:{output.score * 10}%"></div></div>
  <div class="card-label">核心结论</div>
  <div class="judgment">{escape(output.judgment)}</div>
  <div class="card-label">关键依据</div>
  {_html_list(output.key_arguments[:4])}
  <div class="risk-box">
    <strong>主要风险或提醒</strong>
    {_html_list(output.risks[:3])}
  </div>
  {api_error_html}
</div>
        """,
        unsafe_allow_html=True,
    )


def render_summary_card(consensus: ConsensusReport) -> None:
    validation = "需要进一步验证" if consensus.need_validation else "暂不需要优先验证"
    one_line = _summary_sentence(consensus)
    st.markdown(
        f"""
<div class="summary-card">
  <h4>课题总结</h4>
  <div class="summary-meta">
    <span class="level-badge">共识等级：{escape(consensus.consensus_level)}</span>
    <span class="level-badge">置信度：{consensus.confidence_score}/10</span>
    <span class="level-badge">{validation}</span>
  </div>
  <div class="summary-grid">
    <div>
      <div class="card-label">共识点</div>
      {_html_list(consensus.consensus_points)}
    </div>
    <div>
      <div class="card-label">分歧点</div>
      {_html_list(consensus.divergence_points)}
    </div>
  </div>
  <div class="summary-line"><strong>一句话总结：</strong>{escape(one_line)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_market_dashboard(report: FinalReport) -> None:
    st.markdown(
        """
<div class="agent-page-hero">
  <h3>市场研究</h3>
  <p>这里汇总外部搜索摘要、市场趋势、目标客群推断、竞品和替代方案、地区市场机会与首发市场建议。启用联网搜索时，Agent 会主动把产品想法扩展为外部调研问题。</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    _render_market_research_summary(report)

    chart_rows = [
        {"市场地区": item.market_region, "首发适配度": item.launch_fit_score}
        for item in report.market_analysis
        if item.market_region != "全球化进入策略"
    ]
    st.plotly_chart(
        px.bar(pd.DataFrame(chart_rows), x="市场地区", y="首发适配度", range_y=[0, 10], text="首发适配度"),
        use_container_width=True,
    )

    for row in _chunk(report.market_analysis, 2):
        columns = st.columns(len(row))
        for column, market in zip(columns, row):
            with column:
                render_market_card(market)


def render_market_card(market: MarketAnalysis) -> None:
    strategy_class = "strategy" if market.market_region == "全球化进入策略" else ""
    st.markdown(
        f"""
<div class="market-card {strategy_class}">
  <div class="card-meta">
    <div>
      <div class="card-title">{escape(market.market_region)}</div>
      <div class="card-subtitle">{escape(market.launch_recommendation)}</div>
    </div>
    <div class="market-score">{market.launch_fit_score}<span>首发适配度</span></div>
  </div>
  <div class="tag-row">
    <span class="soft-tag">优先级：{escape(market.recommended_priority)}</span>
    <span class="soft-tag">本地化：需评估</span>
  </div>
  <div class="progress-track"><div class="progress-fill" style="width:{market.launch_fit_score * 10}%"></div></div>

  <div class="card-label">需求匹配度</div>
  <div class="insight-box">{escape(market.demand_fit)}</div>
  <div class="card-label">付费意愿</div>
  <div class="insight-box">{escape(market.willingness_to_pay)}</div>
  <div class="card-label">渠道可行性</div>
  <div class="insight-box">{escape(market.channel_feasibility)}</div>
  <div class="card-label">竞争与合规</div>
  <div class="insight-box">{escape(market.competition_pressure)}<br>{escape(market.compliance_risk)}</div>

  <div class="market-grid">
    <div>
      <div class="card-label">主要优势</div>
      {_html_list(market.advantages)}
    </div>
    <div>
      <div class="card-label">主要劣势</div>
      {_html_list(market.disadvantages)}
    </div>
  </div>
  <div class="risk-box">
    <strong>关键风险</strong>
    {_html_list(market.key_risks)}
  </div>
  <div class="decision-box"><strong>进入方式：</strong>{escape(market.recommended_entry_method)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_consensus_table(report: FinalReport) -> None:
    st.subheader("多维对比报告")
    rows = []
    for item in report.consensus_report:
        rows.append(
            {
                "研究课题": item.topic,
                "Agent A 结论": item.agent_a_judgment,
                "Agent B 结论": item.agent_b_judgment,
                "Agent C 结论": item.agent_c_judgment,
                "共识点": "；".join(item.consensus_points),
                "分歧点": "；".join(item.divergence_points),
                "共识等级": item.consensus_level,
                "置信度": item.confidence_score,
                "推演依据 / 数据来源": item.data_source_status,
                "是否需要验证": "是" if item.need_validation else "否",
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_mvp_plan(report: FinalReport) -> None:
    st.markdown(
        """
<div class="agent-page-hero">
  <h3>MVP 验证路径</h3>
  <p>系统从高分歧、低置信度、商业化、市场进入和功能闭环相关判断中提取关键假设，并转化为可执行的低成本实验。</p>
</div>
        """,
        unsafe_allow_html=True,
    )

    st.subheader("关键假设验证清单")
    for row in _chunk(report.mvp_validation_plan, 2):
        columns = st.columns(len(row))
        for column, plan in zip(columns, row):
            with column:
                render_validation_card(plan)

    st.subheader("30 天 MVP 验证计划")
    for row in _chunk(report.thirty_day_plan, 2):
        columns = st.columns(len(row))
        for column, week in zip(columns, row):
            with column:
                render_week_card(week)


def render_validation_card(plan: MVPValidationPlan) -> None:
    priority_class = f"priority-{plan.priority.lower()}"
    st.markdown(
        f"""
<div class="validation-card {priority_class}">
  <div class="card-meta">
    <div>
      <div class="card-title">{escape(plan.hypothesis_name)}</div>
      <div class="card-subtitle">风险等级：{escape(plan.risk_level)} · 优先级：{escape(plan.priority)}</div>
    </div>
    <span class="score-badge">{escape(plan.estimated_duration)}</span>
  </div>
  <div class="hypothesis">{escape(plan.hypothesis_content)}</div>
  <div class="tag-row">
    <span class="soft-tag">成本：{escape(plan.estimated_cost)}</span>
    <span class="soft-tag">方法：{escape(plan.validation_method.split('、')[0])}</span>
  </div>

  <div class="card-label">为什么需要验证</div>
  <div class="insight-box">{escape(plan.why_validate)}</div>
  <div class="card-label">当前依据</div>
  <div class="insight-box">{escape(plan.current_basis)}</div>
  <div class="card-label">推荐验证方式</div>
  <div class="insight-box">{escape(plan.validation_method)}</div>
  <div class="card-label">最小实验设计</div>
  <div class="insight-box">{escape(plan.experiment_design)}</div>

  <div class="validation-grid">
    <div>
      <div class="card-label">目标样本</div>
      <div class="insight-box">{escape(plan.target_sample)}</div>
    </div>
    <div>
      <div class="card-label">成功指标</div>
      <div class="insight-box">{escape(plan.success_metric)}</div>
    </div>
  </div>
  <div class="risk-box"><strong>失败信号</strong><br>{escape(plan.failure_signal)}</div>
  <div class="decision-box"><strong>下一步决策规则：</strong>{escape(plan.decision_rule)}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_week_card(week: dict[str, str]) -> None:
    title = week.get("阶段", "验证阶段")
    items = [f"{key}：{value}" for key, value in week.items() if key != "阶段"]
    st.markdown(
        f"""
<div class="week-card">
  <div class="card-title">{escape(title)}</div>
  <div class="card-label">执行重点</div>
  {_html_list(items)}
</div>
        """,
        unsafe_allow_html=True,
    )


def _html_list(items: list[str]) -> str:
    if not items:
        return "<ul><li>暂无明确内容</li></ul>"
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def _render_market_research_summary(report: FinalReport) -> None:
    search_outputs = [output for output in report.agent_outputs if output.search_enabled and not output.api_error]
    source_status = "联网搜索已启用" if search_outputs else "搜索结果不足，需人工补充资料"
    competitor_outputs = [output for output in report.agent_outputs if "竞品" in output.topic or "替代" in output.topic]
    trend_outputs = [output for output in report.agent_outputs if "趋势" in output.topic or "市场" in output.topic]
    user_outputs = [output for output in report.agent_outputs if "用户" in output.topic or "痛点" in output.topic]
    launch_candidates = [item for item in report.market_analysis if item.market_region != "全球化进入策略"]
    recommended = max(launch_candidates, key=lambda item: item.launch_fit_score) if launch_candidates else None

    columns = st.columns(2)
    with columns[0]:
        st.subheader("外部搜索摘要")
        st.info(f"{source_status}。关键结论需区分来源类型：用户输入、联网搜索、竞品信息、市场趋势信息、模型推理、待验证假设。")
        st.subheader("市场趋势")
        st.write(_first_judgment(trend_outputs, "暂无有效外部趋势摘要，需要补充搜索和人工资料。"))
        st.subheader("目标客群推断")
        st.write(_first_judgment(user_outputs, report.prd_summary.target_users))
    with columns[1]:
        st.subheader("竞品和替代方案")
        st.write(_first_judgment(competitor_outputs, "需要继续搜索直接竞品、间接竞品和用户当前替代方案。"))
        st.subheader("地区市场机会")
        st.write("；".join(f"{item.market_region}：{item.launch_fit_score}/10" for item in launch_candidates))
        st.subheader("首发市场建议")
        st.write(recommended.launch_recommendation + f"：{recommended.market_region}" if recommended else "待验证")


def _first_judgment(outputs: list[AgentOutput], fallback: str) -> str:
    return outputs[0].judgment if outputs else fallback


def _summary_sentence(consensus: ConsensusReport) -> str:
    if consensus.consensus_level == "高分歧":
        return "该课题存在明显分歧，应优先进入 MVP 验证路径，避免过早下结论。"
    if consensus.need_validation:
        return "该课题已有初步方向，但仍需要用低成本实验补足证据。"
    return "该课题当前判断较稳定，可作为后续产品决策的参考锚点。"


def _chunk(items: list, size: int) -> list[list]:
    return [items[index : index + size] for index in range(0, len(items), size)]
