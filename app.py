from __future__ import annotations

from dataclasses import asdict
from html import escape
import json
from pathlib import Path
import re

import pandas as pd
import plotly.express as px
import streamlit as st

from src.document_parser import DocumentParseError, choose_prd_text
from src.gpt_api_client import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    DEFAULT_MODEL_2,
    DEFAULT_MODEL_3,
    DEFAULT_MODEL_4,
    MISSING_KEY_MESSAGE,
    default_model_configs,
    has_api_key,
    get_base_url,
    get_model,
    run_multi_model_market_research,
    run_summary_expert,
)
from src.market_expert import MarketResearchReport


st.set_page_config(
    page_title="产品战略助手",
    page_icon="M",
    layout="wide",
)


RESEARCH_STRUCTURE_OPTIONS = {
    "A版：标准结构版": "standard",
    "B版：自由探索版": "explore",
}
STANDARD_WEB_SECTIONS = [
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
]
EXPLORE_WEB_SECTIONS = [
    "自由探索总览",
    "最值得关注的市场机会",
    "最可能被忽视的用户痛点",
    "最危险的反例或失败风险",
    "可能的产品切入方向",
    "建议下一步验证什么",
    "最终判断",
]

MODEL_CONFIG_PATH = Path(".streamlit/model_config.json")


def _load_model_config() -> dict[str, str]:
    try:
        if MODEL_CONFIG_PATH.exists():
            data = json.loads(MODEL_CONFIG_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {str(key): str(value) for key, value in data.items() if value}
    except (OSError, json.JSONDecodeError):
        return {}
    return {}


def _save_model_config(config: dict[str, str]) -> None:
    clean_config = {key: value for key, value in config.items() if value}
    if not clean_config:
        return
    try:
        MODEL_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        next_text = json.dumps(clean_config, ensure_ascii=False, indent=2)
        if MODEL_CONFIG_PATH.exists() and MODEL_CONFIG_PATH.read_text(encoding="utf-8") == next_text:
            return
        MODEL_CONFIG_PATH.write_text(next_text, encoding="utf-8")
    except OSError:
        st.caption("模型配置暂未保存：当前目录不可写。")


def main() -> None:
    _inject_styles()
    st.title("产品战略助手")
    st.caption("早期产品机会研究 Agent / Early-stage Product Opportunity Research Agent")
    st.write("输入一个早期产品想法，快速判断痛点、用户、市场、竞品、地区、商业化、落地风险与 MVP 验证路径。")
    saved_model_config = _load_model_config()
    if "upload_reset_nonce" not in st.session_state:
        st.session_state["upload_reset_nonce"] = 0
    if "research_result_store" not in st.session_state:
        st.session_state["research_result_store"] = {}

    with st.sidebar:
        st.header("输入区")
        product_name = st.text_input("产品名称", placeholder="例如：AI 会议研究助手")
        product_type = st.selectbox(
            "产品类型",
            ["AI Agent", "软件产品", "硬件产品", "消费电子", "办公效率工具", "其他"],
            index=0,
        )
        run_mode_label = "联网搜索模式"
        run_mode = "web_search"
        research_structure_label = st.radio("研究结构", list(RESEARCH_STRUCTURE_OPTIONS), index=0)
        research_structure = RESEARCH_STRUCTURE_OPTIONS[research_structure_label]
        if research_structure == "standard":
            st.caption("A版适合产品想法较明确时使用：固定维度、稳定完整、方便横向比较。")
        else:
            st.caption("B版适合想法很早期时使用：不固定章节，鼓励模型自由搜索、发散和补充，但保留最低结论要求。")
        api_key = ""
        api_base_url = get_base_url()
        api_model_1 = saved_model_config.get("market_model") or get_model()
        api_model_2 = saved_model_config.get("product_model") or DEFAULT_MODEL_2
        api_model_3 = saved_model_config.get("risk_model") or DEFAULT_MODEL_3
        api_model_4 = saved_model_config.get("summary_model") or DEFAULT_MODEL_4

        api_key = st.text_input("API Key", type="password", value="", placeholder="sk-...", help="留空则读取环境变量 MARKET_RESEARCH_API_KEY / OPENAI_API_KEY。")
        api_base_url = st.text_input("API Base URL", value=api_base_url or DEFAULT_BASE_URL)
        with st.expander("模型角色配置", expanded=True):
            api_model_1 = st.text_input("市场机会研究专家模型", value=api_model_1 or DEFAULT_MODEL, key="market_model_input")
            api_model_2 = st.text_input("产品与竞品研究专家模型", value=api_model_2, key="product_model_input")
            api_model_3 = st.text_input("红队风险与验证专家模型", value=api_model_3, key="risk_model_input")
            api_model_4 = st.text_input("总结专家模型", value=api_model_4 or DEFAULT_MODEL_4, key="summary_model_input")
        if has_api_key(api_key):
            st.success("已检测到 API Key。")
        else:
            st.warning(MISSING_KEY_MESSAGE)

        if st.button("重置上传框", use_container_width=True, help="如果上传控件显示红色失败状态，先点这里清空上传控件，再重新选择文件。"):
            st.session_state["upload_reset_nonce"] += 1
            st.rerun()
        uploaded_file = st.file_uploader(
            "上传产品想法、PRD、概念说明或调研材料",
            type=["txt", "md", "markdown", "csv", "docx", "pdf"],
            accept_multiple_files=False,
            key=f"idea_material_upload_{st.session_state['upload_reset_nonce']}",
            help="支持 .txt、.md、.markdown、.csv、.docx、.pdf。上传后右侧红色 X 是移除按钮，不一定代表失败。",
        )
        if uploaded_file is not None:
            st.caption(f"已选择文件：{uploaded_file.name}（{uploaded_file.size / 1024:.1f} KB）")
        pasted_text = st.text_area(
            "粘贴你的产品想法",
            height=260,
            placeholder="例如：我想做一个面向跨境电商卖家的 AI 选品助手，自动分析趋势、竞品和利润空间。",
        )
        start = st.button("开始产品机会研究", type="primary", use_container_width=True)

    model_names = (api_model_1, api_model_2, api_model_3, api_model_4)
    results_slot = st.empty()
    if start:
        st.session_state["research_run_id"] = st.session_state.get("research_run_id", 0) + 1
        results_slot.empty()
        _save_model_config(
            {
                "market_model": api_model_1.strip(),
                "product_model": api_model_2.strip(),
                "risk_model": api_model_3.strip(),
                "summary_model": api_model_4.strip(),
            }
        )

    if not start:
        with results_slot.container():
            preferred_key = _result_store_key(run_mode, research_structure)
            if preferred_key not in st.session_state["research_result_store"]:
                _render_role_intro(model_names)
            _render_saved_results(
                st.session_state["research_result_store"],
                preferred_key=preferred_key,
            )
        return

    try:
        idea_text, source = choose_prd_text(uploaded_file, pasted_text, "")
    except DocumentParseError as exc:
        with results_slot.container():
            st.error(str(exc))
        return

    if not idea_text:
        with results_slot.container():
            st.warning("请上传材料或输入产品想法。几句话也可以。")
        return

    failed_outputs = []
    if not has_api_key(api_key):
        with results_slot.container():
            st.error(MISSING_KEY_MESSAGE)
        return
    with results_slot.container():
        st.info("正在开始新一轮联网调研；当前版本结果将更新，其他版本结果会保留。")
    with st.spinner("正在调用 3 个模型进行联网搜索市场调研..."):
        web_result = run_multi_model_market_research(
            product_name=product_name,
            product_type=product_type,
            idea_text=idea_text,
            api_key=api_key,
            base_url=api_base_url,
            model_configs=default_model_configs(api_model_1, api_model_2, api_model_3),
            research_structure=research_structure,
        )
    failed_outputs = [output for output in web_result.outputs if output.error]
    with st.spinner("正在调用总结专家提炼核心结论..."):
        summary_result = run_summary_expert(
            product_name=product_name,
            product_type=product_type,
            idea_text=idea_text,
            outputs=web_result.outputs,
            api_key=api_key,
            base_url=api_base_url,
            model=api_model_4,
        )

    result_key = _result_store_key(run_mode, research_structure)
    st.session_state["research_result_store"][result_key] = {
        "source": source,
        "run_mode": run_mode,
        "run_mode_label": run_mode_label,
        "research_structure": research_structure,
        "research_structure_label": research_structure_label,
        "web_result": web_result,
        "summary_result": summary_result,
        "model_names": model_names,
        "report": None,
        "failed_outputs": failed_outputs,
    }

    with results_slot.container():
        _render_saved_results(st.session_state["research_result_store"], preferred_key=result_key)


def _result_store_key(run_mode: str, research_structure: str) -> str:
    return research_structure


def _result_store_label(key: str) -> str:
    return {
        "standard": "A版结果：标准结构",
        "explore": "B版结果：自由探索",
    }.get(key, key)


def _render_saved_results(result_store: dict, preferred_key: str | None = None) -> None:
    if not result_store or not preferred_key or preferred_key not in result_store:
        _render_empty_state()
        return

    _render_result_payload(result_store[preferred_key])


def _render_result_payload(payload: dict) -> None:
    source = payload["source"]
    run_mode = payload["run_mode"]
    run_mode_label = payload["run_mode_label"]
    research_structure = payload["research_structure"]
    research_structure_label = payload["research_structure_label"]
    web_result = payload["web_result"]
    summary_result = payload.get("summary_result")
    report = payload["report"]
    failed_outputs = payload["failed_outputs"]

    if summary_result is not None:
        _render_summary_expert_result(summary_result)
    _render_role_intro(_payload_model_names(payload))
    st.success(f"研究完成。输入来源：{source} · 研究结构：{research_structure_label}")
    if failed_outputs:
        failed_text = "；".join(f"{output.role_name or '模型'}({output.model})：{output.error}" for output in failed_outputs)
        st.warning(f"{len(failed_outputs)} 个模型调用失败：{failed_text}")

    if web_result is not None and research_structure == "explore":
        _render_explore_results_by_model(web_result)
    elif web_result is not None:
        section_names = _web_section_names(research_structure)
        tabs = st.tabs(section_names + ["最终报告"])
        for tab, section_name in zip(tabs[:-1], section_names):
            with tab:
                _render_section_from_web(web_result, section_name)
        with tabs[-1]:
            _render_final_report(report=None, web_result=web_result, key_suffix=research_structure)
    else:
        tabs = st.tabs(["机会总览", "痛点与用户", "市场与竞品", "地区策略", "商业化策略", "落地风险", "MVP 验证", "最终报告"])
        with tabs[0]:
            _render_overview(report)
        with tabs[1]:
            _render_pain_and_users(report)
        with tabs[2]:
            _render_market_and_competitors(report)
        with tabs[3]:
            _render_region_strategy(report)
        with tabs[4]:
            _render_commercialization(report)
        with tabs[5]:
            _render_feasibility(report)
        with tabs[6]:
            _render_mvp(report)
        with tabs[7]:
            _render_final_report(report, key_suffix="local")


def _render_empty_state() -> None:
    return


def _payload_model_names(payload: dict) -> tuple[str, str, str, str]:
    stored = payload.get("model_names")
    if isinstance(stored, (list, tuple)) and len(stored) == 4:
        return tuple(str(item) for item in stored)  # type: ignore[return-value]

    web_result = payload.get("web_result")
    outputs = _web_outputs(web_result)
    model_1 = outputs[0].model if len(outputs) > 0 else DEFAULT_MODEL
    model_2 = outputs[1].model if len(outputs) > 1 else DEFAULT_MODEL_2
    model_3 = outputs[2].model if len(outputs) > 2 else DEFAULT_MODEL_3
    summary_result = payload.get("summary_result")
    model_4 = getattr(summary_result, "model", "") or DEFAULT_MODEL_4
    return (model_1, model_2, model_3, model_4)


def _render_role_intro(model_names: tuple[str, str, str, str]) -> None:
    roles = [
        ("市场机会研究专家", model_names[0], "判断市场价值、行业趋势、地区机会、商业化潜力和市场规模证据。", "role-market"),
        ("产品与竞品研究专家", model_names[1], "推断目标用户、使用场景、竞品替代方案、差异化和产品闭环。", "role-product"),
        ("红队风险与验证专家", model_names[2], "识别伪需求、合规风险、落地风险、反例，并设计 MVP 验证路径。", "role-risk"),
        ("总结专家", model_names[3], "综合前三个模型的结论，提炼简洁、清晰、可决策的核心判断。", "role-summary"),
    ]
    cols = st.columns(4)
    for col, (title, model_name, body, role_class) in zip(cols, roles):
        with col:
            st.markdown(
                f"""
<div class="role-card {role_class}">
  <div class="card-eyebrow">模型角色</div>
  <h4>{escape(title)} <span class="role-model">{escape(model_name or "未配置模型")}</span></h4>
  <p>{escape(body)}</p>
</div>
                """,
                unsafe_allow_html=True,
            )


def _web_section_names(research_structure: str) -> list[str]:
    if research_structure == "explore":
        return EXPLORE_WEB_SECTIONS
    return STANDARD_WEB_SECTIONS


def _render_summary_expert_result(summary_result) -> None:
    if summary_result.error:
        body_html = f'<div class="summary-expert-error">{escape(summary_result.error)}</div>'
    elif summary_result.content:
        body_html = _markdown_to_safe_html(_format_citation_links(summary_result.content))
    else:
        body_html = '<div class="summary-expert-error">总结专家没有返回有效内容。</div>'

    st.markdown(
        f"""
<div class="summary-expert-card role-summary">
  <div class="summary-expert-heading">
    <div>
      <div class="card-eyebrow">总结专家核心结论</div>
      <h3>{escape(summary_result.role_name or "总结专家")}</h3>
    </div>
    <span class="role-model">{escape(summary_result.model or "未配置模型")}</span>
  </div>
  <div class="summary-expert-body">
    {body_html}
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def _markdown_to_safe_html(markdown_text: str) -> str:
    html_lines = []
    current_list = ""

    def close_list() -> None:
        nonlocal current_list
        if current_list:
            html_lines.append(f"</{current_list}>")
            current_list = ""

    def open_list(list_type: str) -> None:
        nonlocal current_list
        if current_list != list_type:
            close_list()
            html_lines.append(f"<{list_type}>")
            current_list = list_type

    for raw_line in (markdown_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            close_list()
            continue

        heading_match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        unordered_match = re.match(r"^\s*[-*•]\s+(.+)$", raw_line)
        ordered_heading_match = re.match(
            r"^\s*\d+[.)]\s*((?:机会方向|产品机会|市场机会|切入方向|方向|场景|方案|路径|建议|风险|反例|验证|结论|目标用户|商业模式).+)$",
            raw_line,
        )
        ordered_match = re.match(r"^\s*\d+[.)]\s+(.+)$", raw_line)

        if heading_match:
            close_list()
            html_lines.append(f"<h4>{_inline_markdown_to_html(heading_match.group(1))}</h4>")
        elif unordered_match:
            open_list("ul")
            html_lines.append(f"<li>{_inline_markdown_to_html(unordered_match.group(1))}</li>")
        elif ordered_heading_match:
            close_list()
            html_lines.append(f"<h4>{_inline_markdown_to_html(ordered_heading_match.group(1))}</h4>")
        elif ordered_match:
            open_list("ol")
            html_lines.append(f"<li>{_inline_markdown_to_html(ordered_match.group(1))}</li>")
        elif _looks_like_summary_heading(line):
            close_list()
            html_lines.append(f"<h4>{_inline_markdown_to_html(line)}</h4>")
        else:
            close_list()
            html_lines.append(f"<p>{_inline_markdown_to_html(line)}</p>")
    close_list()
    return "\n".join(html_lines)


def _render_research_markdown(markdown_text: str, extra_class: str = "") -> None:
    html = _markdown_to_safe_html(_format_citation_links(markdown_text))
    st.markdown(
        f"""
<div class="research-markdown-body {escape(extra_class)}">
  {html}
</div>
        """,
        unsafe_allow_html=True,
    )


def _inline_markdown_to_html(text: str) -> str:
    escaped = escape(text.strip())
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank">\1</a>', escaped)
    return escaped


def _looks_like_summary_heading(line: str) -> bool:
    plain = re.sub(r"[*_`#]+", "", line).strip()
    if not plain:
        return False
    if len(plain) > 34:
        return False
    if re.match(r"^\d+[.)]\s+", plain):
        return False
    heading_keywords = [
        "输入类型",
        "一句话",
        "最终判断",
        "最大风险",
        "核心理由",
        "目标用户",
        "切入场景",
        "下一步",
        "最值得",
        "最容易",
        "产品机会",
        "机会方向",
        "趋势判断",
        "典型场景",
        "深度洞察",
        "探索要点",
        "市场洞察",
        "竞争与替代",
        "商业模式",
        "用户画像",
        "核心假设",
        "验证路径",
        "风险与",
        "机会点",
    ]
    return any(keyword in plain for keyword in heading_keywords) or plain.endswith("：")


def _render_overview(report: MarketResearchReport, is_supplement: bool = False) -> None:
    st.subheader("机会总览")
    if is_supplement:
        st.caption("这里是本地结构化补充，用于把联网调研结果之外的评分、用户分层和 MVP 路径整理成固定结构。")
    summary = report.idea_summary
    cols = st.columns(4)
    cols[0].metric("综合机会评分", f"{report.scorecard.overall_score}/10")
    cols[1].metric("机会等级", report.scorecard.opportunity_level)
    cols[2].metric("最终建议", report.scorecard.recommended_action)
    cols[3].metric("首发市场", report.region_strategy.recommended_first_market)

    st.markdown(f"**一句话定位：** {summary.one_line_positioning}")
    st.markdown(f"**最大亮点：** {report.biggest_highlight}")
    st.markdown(f"**最大风险：** {report.biggest_risk}")
    st.markdown("**下一步最应该做的 3 件事：**")
    st.write(report.scorecard.next_three_actions)

    st.subheader("市场机会评分卡")
    rows = [asdict(item) for item in report.scorecard.items]
    chart_df = pd.DataFrame(rows)
    st.plotly_chart(px.bar(chart_df, x="dimension", y="score", text="score", range_y=[0, 10]), use_container_width=True)
    st.dataframe(chart_df.rename(columns={"dimension": "评分维度", "score": "评分", "rationale": "评分理由"}), use_container_width=True, hide_index=True)

    with st.expander("产品想法摘要与信息缺口", expanded=False):
        st.markdown(f"**产品名称：** {summary.product_name}")
        st.markdown(f"**产品类型：** {summary.product_type}")
        st.markdown("**用户已提供的信息：**")
        st.write(summary.explicit_information)
        st.markdown("**当前信息缺口：**")
        st.write(summary.information_gaps)


def _render_pain_and_users(report: MarketResearchReport, is_supplement: bool = False) -> None:
    pain = report.pain_point
    st.subheader("核心痛点")
    if is_supplement:
        st.caption("以下为本地结构化补充，用于固定展示字段；优先参考上方联网调研结果。")
    st.write(pain.core_pain)
    cols = st.columns(3)
    cols[0].metric("痛点强度", pain.pain_intensity)
    cols[1].metric("痛点频率", pain.pain_frequency)
    cols[2].metric("Must-have 判断", pain.must_have_judgment)
    st.markdown(f"**用户忍受成本：** {pain.user_tolerance_cost}")
    st.markdown("**关键验证问题：**")
    st.write(pain.key_validation_questions)

    st.subheader("目标用户分层")
    for user in report.target_users:
        with st.container(border=True):
            st.markdown(f"#### {user.segment_type}")
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**用户画像：** {user.persona}")
                st.markdown(f"**典型场景：** {user.typical_scenario}")
                st.markdown(f"**购买动机：** {user.purchase_motivation}")
                st.markdown(f"**付费能力：** {user.payment_ability}")
            with c2:
                st.markdown(f"**获客渠道：** {user.acquisition_channel}")
                st.markdown(f"**转化难点：** {user.conversion_difficulty}")
                st.markdown(f"**验证方式：** {user.validation_method}")

    st.subheader("用户当前替代方案")
    st.write(report.alternative_analysis.current_alternatives)


def _render_market_and_competitors(report: MarketResearchReport, is_supplement: bool = False) -> None:
    market = report.market_space
    comp = report.competitor_differentiation
    alt = report.alternative_analysis
    st.subheader("市场空间判断")
    if is_supplement:
        st.caption("以下为本地结构化补充，用于固定展示字段；优先参考上方联网调研结果。")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f"**市场类别：** {market.market_category}")
        st.markdown(f"**市场趋势判断：** {market.trend_direction}")
        st.markdown(f"**市场空间判断：** {market.market_ceiling_judgment}")
        st.markdown(f"**小众到大众扩展：** {market.niche_to_mass_potential}")
    with c2:
        st.markdown("**增长驱动因素：**")
        st.write(market.growth_drivers)
        st.markdown("**需要外部搜索补充的数据：**")
        st.write(market.data_needed)

    st.subheader("竞品与差异化机会")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**直接竞品类型：**")
        st.write(comp.direct_competitor_types)
        st.markdown("**间接竞品类型：**")
        st.write(comp.indirect_competitor_types)
        st.markdown("**替代方案：**")
        st.write(alt.current_alternatives)
    with c2:
        st.markdown("**竞品短板：**")
        st.write(comp.competitor_weaknesses)
        st.markdown("**差异化机会：**")
        st.write(comp.differentiation_directions)
        st.markdown(f"**差异化壁垒强度：** {comp.differentiation_barrier_strength}")
    st.warning("当前本地 Demo 不编造具体公司名称、市场数据或链接；具体竞品后续需通过外部搜索补充。")


def _render_region_strategy(report: MarketResearchReport, is_supplement: bool = False) -> None:
    strategy = report.region_strategy
    st.subheader("地区策略")
    if is_supplement:
        st.caption("以下为本地结构化补充，用于固定展示字段；优先参考上方联网调研结果。")
    rows = [{"地区": item.region, "首发适配度": item.launch_fit_score} for item in strategy.regions]
    st.plotly_chart(px.bar(pd.DataFrame(rows), x="地区", y="首发适配度", text="首发适配度", range_y=[0, 10]), use_container_width=True)

    for region in strategy.regions:
        with st.container(border=True):
            st.markdown(f"#### {region.region}")
            c1, c2 = st.columns([2, 1])
            with c1:
                st.markdown(f"**机会：** {region.opportunity}")
                st.markdown(f"**用户需求差异：** {region.demand_difference}")
                st.markdown(f"**付费意愿：** {region.willingness_to_pay}")
                st.markdown(f"**渠道难度：** {region.channel_difficulty}")
                st.markdown(f"**合规和本地化风险：** {region.compliance_localization_risk}")
                st.markdown(f"**优势：** {'；'.join(region.advantages)}")
                st.markdown(f"**风险：** {'；'.join(region.risks)}")
            with c2:
                st.metric("首发适配度", f"{region.launch_fit_score}/10")

    cols = st.columns(3)
    cols[0].metric("最推荐首发市场", strategy.recommended_first_market)
    cols[1].metric("第二优先市场", strategy.second_priority_market)
    cols[2].metric("暂缓进入市场", strategy.delayed_market)
    st.info(f"推荐进入顺序：{strategy.entry_order}。全球化策略：{strategy.global_strategy}")


def _render_commercialization(report: MarketResearchReport, is_supplement: bool = False) -> None:
    com = report.commercialization
    channels = report.channel_acquisition
    st.subheader("商业化策略")
    if is_supplement:
        st.caption("以下为本地结构化补充，用于固定展示字段；优先参考上方联网调研结果。")
    st.markdown(f"**To C / To B / To B2C 判断：** {com.model_fit}")
    st.markdown("**定价方向：**")
    st.write(com.pricing_models)
    st.markdown(f"**付费意愿判断：** {com.willingness_to_pay}")
    st.markdown(f"**购买阻力：** {com.purchase_resistance}")
    st.markdown(f"**推荐商业化路径：** {com.recommended_path}")
    st.markdown(f"**推荐价格验证方式：** {com.price_validation_method}")

    st.subheader("渠道策略与获客路径")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**推荐渠道：**")
        st.write(channels.recommended_channels)
        st.markdown("**渠道优先级：**")
        st.write(channels.channel_priority)
        st.markdown("**营销卖点：**")
        st.write(channels.marketing_messages)
    with c2:
        st.markdown("**广告素材方向：**")
        st.write(channels.ad_creative_directions)
        st.markdown("**获客难点：**")
        st.write(channels.acquisition_difficulties)
        st.markdown(f"**初期增长策略：** {channels.initial_growth_strategy}")


def _render_feasibility(report: MarketResearchReport, is_supplement: bool = False) -> None:
    risk = report.feasibility_risks
    st.subheader("落地可行性与交付风险")
    if is_supplement:
        st.caption("以下为本地结构化补充，用于固定展示字段；优先参考上方联网调研结果。")
    cards = [
        ("技术风险", risk.technical_risk, "risk-medium"),
        ("供应链风险", risk.supply_chain_risk, "risk-high" if "高" in risk.supply_chain_risk else "risk-low"),
        ("成本风险", risk.cost_risk, "risk-high" if "高" in risk.cost_risk else "risk-medium"),
        ("售后风险", risk.after_sales_risk, "risk-medium"),
        ("用户上手风险", risk.user_experience_risk, "risk-high"),
        ("是否适合先做 MVP", risk.suitable_for_mvp, "risk-low"),
    ]
    for row in _chunk(cards, 3):
        cols = st.columns(len(row))
        for col, (title, body, level_class) in zip(cols, row):
            with col:
                _render_info_card(title, body, level_class)

    st.markdown("#### 最大落地阻碍")
    _render_info_card("优先处理项", risk.biggest_obstacle, "risk-high")


def _render_mvp(report: MarketResearchReport, is_supplement: bool = False) -> None:
    mvp = report.mvp_validation
    st.subheader("关键假设与验证实验")
    if is_supplement:
        st.caption("以下为本地结构化补充，用于固定展示字段；优先参考上方联网调研结果。")
    for row in _chunk(mvp.experiments, 2):
        cols = st.columns(len(row))
        for col, experiment in zip(cols, row):
            with col:
                st.markdown(
                    f"""
<div class="mvp-card">
  <div class="card-eyebrow">关键假设</div>
  <h4>{experiment.hypothesis}</h4>
  <div class="card-section"><strong>验证方法</strong><p>{experiment.validation_method}</p></div>
  <div class="card-grid">
    <div><strong>样本对象</strong><p>{experiment.sample}</p></div>
    <div><strong>周期 / 成本</strong><p>{experiment.estimated_duration} · {experiment.estimated_cost}</p></div>
  </div>
  <div class="card-section success"><strong>成功指标</strong><p>{experiment.success_metric}</p></div>
  <div class="card-section danger"><strong>失败信号</strong><p>{experiment.failure_signal}</p></div>
  <div class="card-section"><strong>决策规则</strong><p>{experiment.decision_rule}</p></div>
</div>
                    """,
                    unsafe_allow_html=True,
                )

    st.subheader("验证方案")
    plan_cards = [
        ("Landing Page 测试方案", mvp.landing_page_test, "risk-low"),
        ("广告买量测试方案", mvp.ad_test, "risk-medium"),
        ("用户访谈方案", mvp.user_interview, "risk-low"),
        ("问卷预调研方案", mvp.survey_test, "risk-low"),
        ("预售 / 等候名单测试方案", mvp.presale_waitlist_test, "risk-medium"),
    ]
    for row in _chunk(plan_cards, 2):
        cols = st.columns(len(row))
        for col, (title, body, level_class) in zip(cols, row):
            with col:
                _render_info_card(title, body, level_class)

    st.subheader("30 天验证计划")
    for row in _chunk(mvp.thirty_day_plan, 2):
        cols = st.columns(len(row))
        for col, week in zip(cols, row):
            with col:
                st.markdown(
                    f"""
<div class="week-card">
  <div class="card-eyebrow">{week.get('阶段', '验证阶段')}</div>
  <h4>{week.get('目标', '')}</h4>
  <div class="card-section"><strong>动作</strong><p>{week.get('动作', '')}</p></div>
  <div class="card-section success"><strong>成功指标</strong><p>{week.get('成功指标', '')}</p></div>
  <div class="card-section"><strong>决策</strong><p>{week.get('决策', '')}</p></div>
</div>
                    """,
                    unsafe_allow_html=True,
                )


def _render_web_research(web_result) -> None:
    st.subheader("联网市场调研")
    cols = st.columns(4)
    cols[0].metric("模型", web_result.model)
    cols[1].metric("状态", web_result.status)
    cols[2].metric("来源数", str(len(web_result.sources)))
    cols[3].metric("检测到搜索", "是" if web_result.search_detected else "否")
    st.caption(f"Base URL：{web_result.base_url}")

    if web_result.error:
        st.error(web_result.error)
    if web_result.content:
        st.markdown(web_result.content)
    else:
        _render_info_card("未获得有效联网调研内容", "搜索失败或模型未返回正文，需要人工核查 API Key、Base URL、模型名和搜索工具权限。", "risk-high")
    if web_result.sources:
        with st.expander("来源摘要", expanded=True):
            for source in web_result.sources:
                st.write(f"- {source}")
    else:
        st.warning("未返回可解析来源摘要；如果模型正文中包含来源，请以模型正文为准。")


def _render_section_from_web(web_result, section_name: str) -> None:
    st.subheader(f"联网调研：{section_name}")
    outputs = _web_outputs(web_result)
    if section_name == "机会总览":
        combined = "\n\n".join(_get_web_section(output, section_name) for output in outputs)
        if combined.strip():
            _render_opportunity_decision_cards(combined)

    st.markdown("#### 三个模型的核心结论")
    for row in _chunk(outputs, 3):
        cards_html = "\n".join(_model_summary_card_html(output, section_name) for output in row)
        st.markdown(
            f"""
<div class="model-summary-grid" style="grid-template-columns: repeat({len(row)}, minmax(0, 1fr));">
{cards_html}
</div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("#### 各模型详细调研结果")
    for output in outputs:
        _render_model_detail_panel(output, section_name)

    all_sources = _web_sources(web_result)
    if section_name == "机会总览" and all_sources:
        with st.expander("联网来源摘要", expanded=False):
            for source in all_sources:
                st.write(f"- {source}")


def _render_explore_results_by_model(web_result) -> None:
    outputs = _web_outputs(web_result)
    tab_labels = [output.role_name or f"模型 {index + 1}" for index, output in enumerate(outputs)]
    tabs = st.tabs(tab_labels)
    for tab, output in zip(tabs, outputs):
        with tab:
            _render_explore_model_result(output)


def _render_explore_model_result(output) -> None:
    role_class = _role_card_class(getattr(output, "role_key", ""))
    st.markdown(
        f"""
<div class="model-detail-header {role_class}">
  <div>
    <div class="model-detail-title">{escape(output.role_name or "联网研究模型")}</div>
    <div class="model-detail-focus">{escape(output.focus or "自由探索式市场研究")}</div>
  </div>
  <div class="model-detail-model">{escape(output.model or "未配置模型")}</div>
</div>
        """,
        unsafe_allow_html=True,
    )
    if output.error:
        st.error(output.error)
    elif output.content:
        _render_research_markdown(output.content, extra_class="explore-result-block")
    else:
        st.warning("该模型没有返回有效内容，请检查模型名、账号权限或搜索能力。")

    if output.sources:
        with st.expander("模型返回的来源摘要", expanded=False):
            for source in output.sources:
                st.write(f"- {source}")


def _render_model_summary_card(output, section_name: str) -> None:
    st.markdown(_model_summary_card_html(output, section_name), unsafe_allow_html=True)


def _model_summary_card_html(output, section_name: str) -> str:
    section = _get_web_section(output, section_name)
    role_class = _role_card_class(getattr(output, "role_key", ""))
    summary = _extract_section_summary(section) if section else output.error or "该模型未按本模块标题返回内容，建议查看最终报告全文。"
    return f"""
<div class="model-summary-card {role_class}">
  <div class="card-eyebrow">{escape(output.role_name or "联网研究模型")}</div>
  <p class="model-focus">{escape(output.focus or "综合市场研究")}</p>
  <div class="summary-text">{escape(summary)}</div>
  <div class="summary-hint">完整调研内容见下方「各模型详细调研结果」。</div>
</div>
    """


def _role_card_class(role_key: str) -> str:
    return {
        "market": "role-market",
        "product": "role-product",
        "risk": "role-risk",
    }.get(role_key, "role-market")


def _render_model_detail_panel(output, section_name: str) -> None:
    section = _get_web_section(output, section_name)
    role_class = _role_card_class(getattr(output, "role_key", ""))
    st.markdown(
        f"""
<div class="model-detail-header {role_class}">
  <div>
    <div class="model-detail-title">{escape(output.role_name or "联网研究模型")}</div>
    <div class="model-detail-focus">{escape(output.focus or "综合市场研究")}</div>
  </div>
  <div class="model-detail-model">{escape(output.model or "未配置模型")}</div>
</div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("展开 / 收起详细调研结果", expanded=True):
        if output.error:
            st.error(output.error)
            return
        if section:
            _render_research_markdown(section)
        elif output.content:
            st.warning("该模型没有按本模块标题返回内容；完整内容可在最终报告中查看。")
        else:
            st.warning("该模型没有返回有效内容，请检查模型名、账号权限或搜索能力。")


def _get_web_section(output, section_name: str) -> str:
    section = output.sections.get(section_name, "")
    if section:
        return section
    content = output.content or ""
    if not content:
        return ""
    if section_name in {"机会总览", "特别注意", "最终建议"}:
        return _short_text(content, 900)
    return ""


def _extract_section_summary(section: str) -> str:
    explicit_finding = _extract_explicit_core_finding(section)
    if explicit_finding:
        return explicit_finding

    judgment_summary = _extract_judgment_summary(section)
    if judgment_summary:
        return judgment_summary

    table_summary = _extract_table_summary(section)
    if table_summary:
        return f"核心发现：{table_summary}"

    return "该模型未形成可自动提炼的核心发现，建议查看下方详细调研结果。"


def _extract_explicit_core_finding(section: str) -> str:
    patterns = [
        r"(?:核心发现|核心结论|总体判断|关键发现|一句话结论)[：:]\s*(.+)",
        r"\*\*(?:核心发现|核心结论|总体判断|关键发现|一句话结论)[：:]\*\*\s*(.+)",
    ]
    for raw_line in (section or "").splitlines():
        line = _clean_summary_line(raw_line)
        if not line:
            continue
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return _short_text(match.group(1).strip(), 260)
    return ""


def _extract_judgment_summary(section: str) -> str:
    candidates = []
    for raw_line in (section or "").splitlines():
        line = _clean_summary_line(raw_line)
        if not line:
            continue
        if re.search(r"(值得|谨慎|不建议|优先|机会|风险|差异化|成熟|不足|可行|不可行|适合|不适合|建议|关键|核心|验证|付费|增长|壁垒|合规|获客)", line):
            candidates.append(line)
        if len(candidates) >= 2:
            break
    if not candidates:
        return ""
    return _short_text("核心发现：" + "；".join(candidates), 260)


def _clean_summary_line(raw_line: str) -> str:
    line = (raw_line or "").strip()
    if not line or line.startswith("### 引用来源") or line.startswith("## 来源摘要"):
        return ""
    if _is_markdown_table_line(line) or re.match(r"^#{1,6}\s*", line):
        return ""
    line = re.sub(r"^[-*#\s]+", "", line).strip()
    line = re.sub(r"\*\*", "", line).strip()
    line = re.sub(r"^\d+[.、]\s*[^：:]{2,14}[：:]\s*", "", line).strip()
    line = re.sub(r"^(市场概况|直接竞品|间接竞品|数据来源|引用来源|说明|项目|维度|判断)[：:]\s*", "", line).strip()
    if re.fullmatch(r"[：:，,。;；|\\/\s]+", line):
        return ""
    return line


def _extract_table_summary(section: str) -> str:
    rows = []
    for raw_line in (section or "").splitlines():
        line = raw_line.strip()
        if not _is_markdown_table_line(line):
            continue
        cells = [re.sub(r"\*\*", "", cell).strip() for cell in line.strip("|").split("|")]
        cells = [cell for cell in cells if cell]
        if not cells or all(re.fullmatch(r"[-:\s]+", cell) for cell in cells):
            continue
        if any(cell in {"项目", "说明", "收入模型", "单位", "模式", "策略", "维度", "判断"} for cell in cells):
            continue
        rows.append(cells)
        if len(rows) >= 2:
            break
    if not rows:
        return ""

    summaries = []
    for cells in rows:
        if len(cells) >= 3:
            summaries.append(f"{cells[0]}：{cells[1]}，{cells[2]}")
        elif len(cells) == 2:
            summaries.append(f"{cells[0]}：{cells[1]}")
        else:
            summaries.append(cells[0])
    return _short_text("；".join(summaries), 180)


def _is_markdown_table_line(line: str) -> bool:
    return line.startswith("|") and line.endswith("|") and line.count("|") >= 2


def _format_citation_links(markdown_text: str) -> str:
    return "\n".join(_linkify_plain_url(line) for line in (markdown_text or "").splitlines())


def _linkify_plain_url(line: str) -> str:
    if "http" not in line or "](" in line:
        return line
    match = re.search(r"https?://[^\s)）\]<>]+", line)
    if not match:
        return line

    url = match.group(0).rstrip(".,;，。；")
    prefix = line[: match.start()].rstrip(" ｜|:：")
    suffix = line[match.end() :]
    if prefix:
        return f"{prefix}｜[链接]({url}){suffix}"
    return line.replace(url, f"[{url}]({url})", 1)


def _render_opportunity_decision_cards(section: str) -> None:
    score = _clean_card_value(_extract_first_match(section, [r"市场价值评分[：:\s]*([0-9]+(?:\.[0-9]+)?)", r"([0-9]+(?:\.[0-9]+)?)\s*/\s*10"]))
    decision = _clean_card_value(_extract_first_match(section, [r"是否值得推进[：:\s]*(.+)", r"最终建议[：:\s]*(.+)"]))
    audience = _clean_card_value(_extract_first_match(section, [r"核心目标人群[：:\s]*(.+)", r"目标人群[：:\s]*(.+)"]))
    market = _clean_card_value(_extract_first_match(section, [r"优先首发市场[：:\s]*(.+)", r"优先市场[：:\s]*(.+)"]))
    path = _clean_card_value(_extract_first_match(section, [r"推荐推进路径[：:\s]*(.+)", r"推进路径[：:\s]*(.+)"]))

    cards = []
    if score:
        cards.append(("市场价值评分", _short_text(f"{score}/10" if "/10" not in score else score, 80), "risk-low"))
    if decision:
        cards.append(("推进结论", decision, "risk-medium"))
    if audience:
        cards.append(("核心目标人群", audience, "risk-low"))
    if market:
        cards.append(("优先市场", market, "risk-medium"))

    for row in _chunk(cards, 4):
        cols = st.columns(len(row))
        for col, (title, body, level_class) in zip(cols, row):
            with col:
                _render_info_card(title, body, level_class, scrollable=True)
    if path:
        _render_info_card("怎么推进这个项目", path, "risk-low", scrollable=True)


def _web_markdown_appendix(web_result) -> str:
    if web_result is None:
        return ""
    if hasattr(web_result, "outputs"):
        lines = ["", "## 三模型联网搜索市场调研", ""]
        for output in web_result.outputs:
            lines.extend(
                [
                    f"### {output.role_name or '联网研究模型'}",
                    f"- 模型：{output.model}",
                    f"- 视角：{output.focus}",
                    f"- 状态：{output.status}",
                    f"- 是否检测到搜索调用或来源：{'是' if output.search_detected else '否'}",
                ]
            )
            if output.error:
                lines.append(f"- 错误：{output.error}")
            if output.sources:
                lines.append(f"- 来源摘要：{'; '.join(output.sources)}")
            else:
                lines.append("- 来源摘要：搜索结果不足或未返回可解析来源，需要人工核查。")
            if output.content:
                lines.extend(["", _format_citation_links(output.content), ""])
        return "\n".join(lines)
    lines = [
        "",
        "## 联网搜索市场调研附录",
        "",
        f"- 模型：{web_result.model}",
        f"- Base URL：{web_result.base_url}",
        f"- 状态：{web_result.status}",
        f"- 是否检测到搜索调用或来源：{'是' if web_result.search_detected else '否'}",
    ]
    if web_result.error:
        lines.append(f"- 错误：{web_result.error}")
    if web_result.sources:
        lines.append(f"- 来源摘要：{'; '.join(web_result.sources)}")
    else:
        lines.append("- 来源摘要：搜索结果不足或未返回可解析来源，需要人工核查。")
    if web_result.content:
        lines.extend(["", _format_citation_links(web_result.content), ""])
    return "\n".join(lines)


def _web_outputs(web_result) -> list:
    if web_result is None:
        return []
    if hasattr(web_result, "outputs"):
        return list(web_result.outputs)
    return [web_result]


def _web_sources(web_result) -> list[str]:
    sources: list[str] = []
    for output in _web_outputs(web_result):
        for source in getattr(output, "sources", []):
            if source not in sources:
                sources.append(source)
    return sources


def _render_final_report(report: MarketResearchReport | None, web_result=None, key_suffix: str = "") -> None:
    st.subheader("适合复制到 Word 或 PPT 的完整结构化报告")
    if web_result is not None:
        report_text = _web_markdown_appendix(web_result)
    else:
        report_text = report.markdown_report if report is not None else ""
    st.download_button(
        "下载 Markdown 报告",
        data=report_text.encode("utf-8"),
        file_name="product_opportunity_research_report.md",
        mime="text/markdown",
        key=f"download_report_{key_suffix or 'default'}",
    )
    st.text_area("可复制报告正文", report_text, height=760, key=f"report_text_{key_suffix or 'default'}")


def _inject_styles() -> None:
    st.markdown(
        """
<style>
  .block-container { padding-top: 2rem; }
  div[data-testid="stMetric"] {
    border: 1px solid #dde5f0;
    border-radius: 8px;
    padding: 14px 16px;
    background: #ffffff;
  }
  div[data-testid="stVerticalBlockBorderWrapper"] { border-radius: 8px; }
  .info-card,
  .role-card,
  .model-summary-card,
  .mvp-card,
  .week-card {
    border: 1px solid #dde5f0;
    border-radius: 8px;
    background: #ffffff;
    padding: 16px;
    min-height: 190px;
    margin-bottom: 14px;
    box-shadow: 0 8px 20px rgba(16, 24, 40, 0.05);
  }
  .info-card h4,
  .role-card h4,
  .model-summary-card h4,
  .mvp-card h4,
  .week-card h4 {
    margin: 4px 0 12px 0;
    font-size: 1rem;
    color: #111827;
    line-height: 1.35;
  }
  .info-card p,
  .role-card p,
  .model-summary-card p,
  .mvp-card p,
  .week-card p {
    margin: 4px 0 0 0;
    color: #334155;
    line-height: 1.55;
    font-size: 0.92rem;
  }
  .info-card.scrollable-card {
    height: 230px;
    max-height: 230px;
    overflow-y: auto;
  }
  .info-card.scrollable-card p {
    padding-right: 6px;
  }
  .card-eyebrow {
    color: #64748b;
    font-size: 0.76rem;
    font-weight: 800;
    letter-spacing: 0;
  }
  .card-section {
    border-top: 1px solid #e5edf7;
    padding-top: 10px;
    margin-top: 10px;
  }
  .card-section strong,
  .card-grid strong {
    color: #1f2937;
    font-size: 0.82rem;
  }
  .card-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    border-top: 1px solid #e5edf7;
    padding-top: 10px;
    margin-top: 10px;
  }
  .risk-high { border-top: 4px solid #d85b43; }
  .risk-medium { border-top: 4px solid #f59e0b; }
  .risk-low { border-top: 4px solid #00a389; }
  .success {
    background: #eef8f5;
    border: 1px solid #bfe5dc;
    border-radius: 8px;
    padding: 10px;
  }
  .danger {
    background: #fff7ed;
    border: 1px solid #fed7aa;
    border-radius: 8px;
    padding: 10px;
  }
  .model-summary-card {
    min-height: 240px;
    height: auto;
    overflow: visible;
    display: flex;
    flex-direction: column;
  }
  .model-summary-grid {
    display: grid;
    gap: 24px;
    align-items: stretch;
    margin-bottom: 18px;
  }
  .model-summary-grid .model-summary-card {
    height: 100%;
    margin-bottom: 0;
  }
  .role-card {
    min-height: 278px;
    height: 278px;
    display: flex;
    flex-direction: column;
  }
  .role-card,
  .model-summary-card {
    border-top-width: 5px;
  }
  .role-market {
    border-color: #bde7de;
    border-top-color: #00a389;
    background: linear-gradient(180deg, #f5fffc 0%, #ffffff 55%);
  }
  .role-product {
    border-color: #cfe0ff;
    border-top-color: #2f6fed;
    background: linear-gradient(180deg, #f6f9ff 0%, #ffffff 55%);
  }
  .role-risk {
    border-color: #ffd8b1;
    border-top-color: #f59e0b;
    background: linear-gradient(180deg, #fffaf2 0%, #ffffff 55%);
  }
  .role-summary {
    border-color: #d8ccff;
    border-top-color: #7c3aed;
    background: linear-gradient(180deg, #faf7ff 0%, #ffffff 55%);
  }
  .role-model {
    display: inline-block;
    max-width: 100%;
    margin-left: 6px;
    padding: 2px 7px;
    border-radius: 999px;
    background: rgba(100, 116, 139, 0.12);
    color: #475569;
    font-size: 0.72rem;
    font-weight: 700;
    line-height: 1.4;
    vertical-align: middle;
    word-break: break-word;
  }
  .role-card p {
    margin-top: 16px;
  }
  .model-summary-card h4 {
    font-size: 0.95rem;
    line-height: 1.3;
    word-break: break-word;
  }
  .model-focus {
    font-size: 0.84rem !important;
    color: #64748b !important;
    line-height: 1.45 !important;
    margin-bottom: 10px !important;
  }
  .summary-text {
    border-top: 1px solid #e5edf7;
    padding-top: 10px;
    color: #263449;
    font-size: 0.92rem;
    line-height: 1.6;
    overflow: visible;
    word-break: break-word;
  }
  .summary-hint {
    margin-top: auto;
    padding-top: 12px;
    color: #64748b;
    font-size: 0.78rem;
    line-height: 1.4;
  }
  .model-detail-header {
    border: 1px solid #dde5f0;
    border-top-width: 5px;
    border-radius: 8px 8px 0 0;
    padding: 14px 16px;
    margin-top: 14px;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 14px;
  }
  .summary-expert-card {
    border: 1px solid #d8ccff;
    border-top: 5px solid #7c3aed;
    border-radius: 8px;
    padding: 20px 22px;
    margin: 12px 0 22px 0;
    background: linear-gradient(180deg, #faf7ff 0%, #ffffff 72%);
    box-shadow: 0 12px 28px rgba(91, 33, 182, 0.08);
  }
  .summary-expert-heading {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 16px;
  }
  .summary-expert-heading h3 {
    margin: 4px 0 0 0;
    font-size: 1.08rem;
    color: #111827;
  }
  .summary-expert-body {
    border-top: 1px solid #eadfff;
    margin-top: 16px;
    padding-top: 16px;
    color: #263449;
  }
  .summary-expert-body p,
  .summary-expert-body li,
  .research-markdown-body p,
  .research-markdown-body li {
    font-size: 0.96rem;
    line-height: 1.72;
    margin: 0 0 8px 0;
  }
  .summary-expert-body h4,
  .research-markdown-body h4 {
    color: #111827;
    font-size: 1.08rem;
    font-weight: 900;
    line-height: 1.35;
    margin: 20px 0 8px 0;
  }
  .summary-expert-body h4:first-child,
  .research-markdown-body h4:first-child {
    margin-top: 0;
  }
  .summary-expert-body ul,
  .summary-expert-body ol,
  .research-markdown-body ul,
  .research-markdown-body ol {
    padding-left: 1.35rem;
    margin: 0 0 12px 0;
  }
  .research-markdown-body h4 + ul,
  .research-markdown-body h4 + ol,
  .summary-expert-body h4 + ul,
  .summary-expert-body h4 + ol {
    margin-top: 2px;
  }
  .summary-expert-body li,
  .research-markdown-body li {
    padding-left: 0.12rem;
  }
  .summary-expert-body li + li,
  .research-markdown-body li + li {
    margin-top: 6px;
  }
  .summary-expert-body strong {
    color: #111827;
  }
  .summary-expert-body a {
    color: #5b21b6;
    text-decoration: none;
    font-weight: 700;
  }
  .summary-expert-error {
    color: #b42318;
    background: #fff1f1;
    border: 1px solid #ffd0d0;
    border-radius: 8px;
    padding: 10px 12px;
  }
  .model-detail-title {
    color: #111827;
    font-size: 1.08rem;
    font-weight: 850;
    line-height: 1.35;
  }
  .model-detail-focus {
    color: #64748b;
    font-size: 0.86rem;
    line-height: 1.45;
    margin-top: 4px;
  }
  .model-detail-model {
    flex: 0 0 auto;
    max-width: 46%;
    padding: 5px 10px;
    border-radius: 999px;
    background: rgba(100, 116, 139, 0.12);
    color: #334155;
    font-size: 0.78rem;
    font-weight: 800;
    line-height: 1.35;
    word-break: break-word;
    text-align: right;
  }
  div[data-testid="stExpander"] details {
    border-radius: 8px;
    border-color: #dde5f0;
  }
  .model-detail-header + div[data-testid="stExpander"] details {
    border-top-left-radius: 0;
    border-top-right-radius: 0;
    border-top: 0;
  }
  .explore-result-block {
    border: 1px solid #dde5f0;
    border-top: 0;
    border-radius: 0 0 8px 8px;
    padding: 20px 24px;
    background: #ffffff;
    margin-bottom: 18px;
  }
  div[data-testid="stMarkdown"] h1,
  div[data-testid="stMarkdown"] h2,
  div[data-testid="stMarkdown"] h3,
  div[data-testid="stMarkdown"] h4,
  .research-markdown-body h1,
  .research-markdown-body h2,
  .research-markdown-body h3,
  .research-markdown-body h4,
  div[data-testid="stExpander"] h1,
  div[data-testid="stExpander"] h2,
  div[data-testid="stExpander"] h3,
  div[data-testid="stExpander"] h4,
  .explore-result-block h1,
  .explore-result-block h2,
  .explore-result-block h3,
  .explore-result-block h4 {
    color: #111827 !important;
    font-weight: 900 !important;
    line-height: 1.35 !important;
    letter-spacing: 0 !important;
  }
  div[data-testid="stMarkdown"] h1,
  div[data-testid="stMarkdown"] h2,
  .research-markdown-body h1,
  .research-markdown-body h2,
  div[data-testid="stExpander"] h1,
  div[data-testid="stExpander"] h2,
  .explore-result-block h1,
  .explore-result-block h2 {
    font-size: 1.42rem !important;
    margin-top: 1.8rem !important;
    margin-bottom: 0.72rem !important;
    padding-top: 1.1rem;
    border-top: 1px solid #e5e7eb;
  }
  div[data-testid="stMarkdown"] h1:first-child,
  div[data-testid="stMarkdown"] h2:first-child,
  .research-markdown-body h1:first-child,
  .research-markdown-body h2:first-child,
  div[data-testid="stExpander"] h1:first-child,
  div[data-testid="stExpander"] h2:first-child,
  .explore-result-block h1:first-child,
  .explore-result-block h2:first-child {
    margin-top: 0.2rem !important;
    padding-top: 0;
    border-top: 0;
  }
  div[data-testid="stMarkdown"] h3,
  .research-markdown-body h3,
  div[data-testid="stExpander"] h3,
  .explore-result-block h3 {
    font-size: 1.04rem !important;
    margin-top: 1.05rem !important;
    margin-bottom: 0.48rem !important;
  }
  div[data-testid="stMarkdown"] h4,
  .research-markdown-body h4,
  div[data-testid="stExpander"] h4,
  .explore-result-block h4 {
    font-size: 0.98rem !important;
    margin-top: 0.9rem !important;
    margin-bottom: 0.36rem !important;
  }
  div[data-testid="stMarkdown"] p,
  div[data-testid="stMarkdown"] li,
  .research-markdown-body p,
  .research-markdown-body li,
  div[data-testid="stExpander"] p,
  div[data-testid="stExpander"] li,
  .explore-result-block p,
  .explore-result-block li {
    color: #111827;
    font-size: 0.96rem;
    line-height: 1.72;
  }
  div[data-testid="stMarkdown"] ul,
  div[data-testid="stMarkdown"] ol,
  .research-markdown-body ul,
  .research-markdown-body ol,
  div[data-testid="stExpander"] ul,
  div[data-testid="stExpander"] ol,
  .summary-expert-body ul,
  .summary-expert-body ol,
  .explore-result-block ul,
  .explore-result-block ol {
    padding-left: 1.35rem !important;
    margin-left: 0 !important;
  }
  div[data-testid="stMarkdown"] li,
  .research-markdown-body li,
  div[data-testid="stExpander"] li,
  .summary-expert-body li,
  .explore-result-block li {
    padding-left: 0.12rem !important;
    margin-left: 0 !important;
  }
  div[data-testid="stMarkdown"] strong,
  .research-markdown-body strong,
  div[data-testid="stExpander"] strong,
  .explore-result-block strong {
    color: #111827;
    font-weight: 850;
  }
  .info-card h4,
  .role-card h4,
  .model-summary-card h4,
  .mvp-card h4,
  .week-card h4 {
    margin: 4px 0 12px 0 !important;
    padding-top: 0 !important;
    border-top: 0 !important;
    font-size: 1rem !important;
    line-height: 1.35 !important;
  }
  @media (max-width: 900px) {
    .model-summary-grid {
      grid-template-columns: 1fr !important;
    }
  }
</style>
        """,
        unsafe_allow_html=True,
    )


def _render_info_card(title: str, body: str, level_class: str = "risk-medium", scrollable: bool = False) -> None:
    extra_class = "scrollable-card" if scrollable else ""
    st.markdown(
        f"""
<div class="info-card {level_class} {extra_class}">
  <div class="card-eyebrow">判断项</div>
  <h4>{title}</h4>
  <p>{body}</p>
</div>
        """,
        unsafe_allow_html=True,
    )


def _extract_first_match(text: str, patterns: list[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip().strip("*- ")
    return ""


def _clean_card_value(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value or "").strip()
    cleaned = cleaned.strip("*-_：:，,。;；| ")
    if not cleaned:
        return ""
    invalid_values = {
        "见下方结论",
        "未说明",
        "输入中未说明",
        "待补充",
        "无",
        "暂无",
        "n/a",
        "none",
    }
    if cleaned.lower() in invalid_values:
        return ""
    if re.fullmatch(r"[：:，,。;；|\\/\s]+", cleaned):
        return ""
    return cleaned


def _short_text(text: str, max_length: int) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    return cleaned if len(cleaned) <= max_length else cleaned[: max_length - 1] + "…"


def _chunk(items: list, size: int) -> list[list]:
    return [items[index : index + size] for index in range(0, len(items), size)]


if __name__ == "__main__":
    main()
