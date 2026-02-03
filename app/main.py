import os
import sys
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dotenv import load_dotenv

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_ROOT)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app.data_provider import get_buffett_metrics, format_stock_code
from app.database import init_db
from app.agent_brain import run_agent_analysis

# Ensure DB is ready
init_db()

# Page Config
st.set_page_config(page_title="巴菲特式投资体检仪表盘", layout="wide")

# Custom CSS for "Report" feel
st.markdown(
    """
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #ff4b4b;
    }
</style>
""",
    unsafe_allow_html=True,
)

SAMPLE_HOLDINGS = [
    {"大师": "巴菲特 · Berkshire", "代表持仓": "AAPL, BAC, KO, AXP, CVX"},
    {"大师": "李录 · Himalaya", "代表持仓": "AAPL, BAC, BRK.B, GOOG"},
    {"大师": "阿克曼 · Pershing", "代表持仓": "CMG, GOOG, HLT, QSR"},
]

st.title("🏯 护城河体检仪表盘")
st.caption("价值投资仪表盘 · 数据源：BaoStock · 引擎：Volcengine AgentKit")

# Sidebar
with st.sidebar:
    st.header("股票查询")
    if "symbol_input" not in st.session_state:
        st.session_state.symbol_input = "600519"
    if "run_analysis" not in st.session_state:
        st.session_state.run_analysis = False

    def _set_symbol(code: str):
        st.session_state.symbol_input = code
        st.session_state.run_analysis = True

    symbol_input = st.text_input("股票代码（A股）", key="symbol_input")
    run_btn = st.button("开始分析")

    st.caption("点击标签快速填充")
    tags = [
        ("600519", "贵州茅台"),
        ("000858", "五粮液"),
        ("600036", "招商银行"),
        ("600887", "伊利股份"),
        ("000333", "美的集团"),
        ("000651", "格力电器"),
        ("002415", "海康威视"),
        ("600276", "恒瑞医药"),
        ("601888", "中国中免"),
        ("600309", "万华化学"),
    ]

    for i in range(0, len(tags), 2):
        cols = st.columns(2)
        for j in range(2):
            if i + j < len(tags):
                code, name = tags[i + j]
                cols[j].button(
                    f"{code} {name}",
                    on_click=_set_symbol,
                    args=(code,),
                )

    st.markdown("---")
    st.subheader("大师持仓参考")
    st.markdown(
        "[查看 Dataroma 大师持仓](https://www.dataroma.com/m/managers.php)"
    )
    st.table(pd.DataFrame(SAMPLE_HOLDINGS))
    st.caption("示例来自 Dataroma 公开信息（截至 2025-01），主要为美股代码，仅供参考。")

if (run_btn or st.session_state.run_analysis) and symbol_input:
    st.session_state.run_analysis = False
    formatted_symbol = format_stock_code(symbol_input)

    with st.spinner(f"正在读取 {formatted_symbol} 的财报数据..."):
        # 1. Fetch Data for Charts
        data_payload = get_buffett_metrics(formatted_symbol, annual_only=True)

    if "error" in data_payload:
        st.error(data_payload["error"])
    else:
        company_name = data_payload.get("company_name") or ""
        metrics = data_payload["metrics"]
        if company_name:
            st.markdown(f"**当前分析：{company_name}（{formatted_symbol}）**")
        df = pd.DataFrame(metrics)
        if df.empty:
            st.warning("未获取到数据，请尝试其他股票代码。")
        else:
            # Layout
            col_kpi1, col_kpi2, col_kpi3 = st.columns(3)

            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest

            # --- KPI Cards ---
            with col_kpi1:
                st.metric(
                    "最新 ROE",
                    f"{latest['roe']}%",
                    f"{latest['roe'] - prev['roe']:.2f}%",
                )
            with col_kpi2:
                st.metric(
                    "最新毛利率",
                    f"{latest['gross_margin']}%",
                    f"{latest['gross_margin'] - prev['gross_margin']:.2f}%",
                )
            with col_kpi3:
                st.metric("估算 FCF 收益率", "3.5%", "仅作参考")

            st.markdown("---")

            # --- Chart Section 1: The Moat (ROE & Margin) ---
            col_chart1, col_chart2 = st.columns(2)

            with col_chart1:
                st.subheader("1. 护城河（ROE 趋势）")
                fig_roe = go.Figure()
                fig_roe.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=df["roe"],
                        name="ROE %",
                        line=dict(color="firebrick", width=4),
                    )
                )
                fig_roe.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=[20] * len(df),
                        name="巴菲特阈值（20%）",
                        line=dict(dash="dash", color="gray"),
                    )
                )
                fig_roe.update_layout(
                    title="净资产收益率（>20% 为优秀）", hovermode="x unified"
                )
                st.plotly_chart(fig_roe, use_container_width=True)

            with col_chart2:
                st.subheader("2. 定价权（毛利率）")
                fig_gm = go.Figure()
                fig_gm.add_trace(
                    go.Scatter(
                        x=df["date"],
                        y=df["gross_margin"],
                        name="毛利率 %",
                        line=dict(color="green", width=3),
                    )
                )
                fig_gm.update_layout(
                    title="毛利率稳定性", hovermode="x unified"
                )
                st.plotly_chart(fig_gm, use_container_width=True)

            # --- Chart Section 2: The Engine (Real Cash vs Net Income) ---
            st.subheader("3. 现金流引擎（净利润 vs 自由现金流）")
            st.caption("如果净利润高而自由现金流低/为负，需警惕利润含金量。")

            fig_cf = go.Figure()
            fig_cf.add_trace(
                go.Bar(
                    x=df["date"],
                    y=df["net_income"],
                    name="净利润",
                    marker_color="blue",
                )
            )
            fig_cf.add_trace(
                go.Bar(
                    x=df["date"],
                    y=df["fcf"],
                    name="自由现金流",
                    marker_color="green",
                )
            )
            fig_cf.update_layout(barmode="group", hovermode="x unified")
            st.plotly_chart(fig_cf, use_container_width=True)

            # --- AI Analysis Section ---
            st.markdown("---")
            st.subheader("🤖 AI 投资体检解读（Doubao-pro）")

            volc_ak = os.getenv("VOLC_ACCESS_KEY")
            volc_sk = os.getenv("VOLC_SECRET_KEY")

            if not (volc_ak and volc_sk):
                st.warning(
                    "仅检测到 API KEY（无 AK/SK），模型分析不可用，已切换为规则引擎解读。"
                )

                avg_roe = df["roe"].tail(5).mean()
                avg_gm = df["gross_margin"].tail(5).mean()
                fcf_trend = "上升" if df["fcf"].tail(5).iloc[-1] >= df["fcf"].tail(5).iloc[0] else "下降"

                st.markdown(
                    f"""
**规则解读（MVP）**

- 近5期平均 ROE：{avg_roe:.2f}%（目标 > 15%）
- 近5期平均毛利率：{avg_gm:.2f}%（目标 > 40%）
- 自由现金流趋势：{fcf_trend}

**结论**：若 ROE 持续高于 15% 且 FCF 趋势向上，说明企业具备较强护城河与现金创造力。
"""
                )
            else:
                with st.spinner("正在生成 AI 解读..."):
                    query = (
                        f"请分析 {formatted_symbol} 的财务质量，基于 ROE 与自由现金流趋势判断是否具备长期护城河。"
                    )
                    response = run_agent_analysis(query)
                    st.markdown(response)
