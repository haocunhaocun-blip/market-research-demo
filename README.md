# Meta Product Opportunity Research Agent Demo

早期产品机会研究 Agent / Early-stage Product Opportunity Research Agent。

当前版本是本地可运行的单一市场研究专家架构，用于判断一个早期产品想法是否值得继续推进。它不是 PRD 完整性检查器，而是围绕痛点、用户、市场、竞品、商业化、渠道、地区、落地风险和 MVP 验证做结构化推演。

## 当前运行模式

### 1. 本地 Demo 模式

默认模式，不调用任何 API，不联网搜索，不调用 AIHubMix。

所有相关判断标注为：

> 本地 Demo 模式：基于产品想法与商业逻辑推演，暂无外部数据支撑。

### 2. 联网搜索模式

运行时不在页面输入 API Key。系统自动从环境变量或 Streamlit secrets 读取：

- `MARKET_RESEARCH_API_KEY` 或 `OPENAI_API_KEY`
- `MARKET_RESEARCH_API_BASE_URL`，默认 `https://aihubmix.com/v1`
- `MARKET_RESEARCH_MODEL`，默认 `deepseek-v4-flash:surfing`

当前实现支持：

- OpenAI 官方 Responses API：`tools=[{"type": "web_search"}]`
- 强制 `tool_choice="required"`，要求模型调用联网搜索工具
- AIHubMix `:surfing` 模型：使用 Chat Completions 调用，搜索能力由模型名后缀启用

无 Key 时提示：

> 当前未配置 MARKET_RESEARCH_API_KEY 或 OPENAI_API_KEY，无法使用联网搜索模式。

如果搜索失败，系统会标注：

> 搜索失败，需要人工核查。

## 分析框架

系统当前覆盖 10 个核心维度：

1. 痛点真实性判断
2. 目标用户判断
3. 市场空间判断
4. 替代方案与切换价值分析
5. 竞品与差异化机会
6. 商业化可行性判断
7. 渠道与获客可行性分析
8. 地区市场选择
9. 落地可行性与交付风险
10. MVP 验证路径

并输出 8 项市场机会评分卡：

1. 痛点强度
2. 需求频率
3. 目标用户清晰度
4. 市场增长潜力
5. 差异化程度
6. 付费可能性
7. 渠道可达性
8. 落地可行性

## 页面结构

- 机会总览
- 痛点与用户
- 市场与竞品
- 地区策略
- 商业化策略
- 落地风险
- MVP 验证
- 最终报告

## 运行

```powershell
cd e:\vibecoding
streamlit run app.py
```
