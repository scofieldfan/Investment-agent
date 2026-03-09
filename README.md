# 巴菲特式投资体检仪表盘（MVP）

一个面向 A 股的"企业体检"仪表盘，重点关注 **ROE、毛利率、现金流** 等长期质量指标。界面简洁，支持输入股票代码或点击标签快速分析。

> 数据源：BaoStock  
> 引擎：Volcengine AgentKit（可选）

---

## 功能概览

- **护城河监测**：ROE 趋势、毛利率稳定性
- **现金流引擎**：净利润 vs 自由现金流（当前为估算值）
- **规则引擎解读**：无 AK/SK 时自动启用
- **快速标签**：常见巴菲特风格公司公司一键分析
- **大师持仓参考**：Dataroma 持仓链接与示例持仓
- **第三方交易API**：从外部API获取实时股票数据

---

## 运行环境

- macOS / Linux / Windows
- Python 3.9+（推荐 3.12）

---

## 安装与启动

```bash
# 进入项目
cd /root/.openclaw/workspace/Investment-agent

# 创建并激活虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
python -m pip install -r requirements.txt

# 启动
streamlit run app/main.py
```

启动后在浏览器打开：

```
http://localhost:8502
```

---

## 配置说明

在项目根目录创建 `.env`：

```
ARK_API_KEY=你的APIKEY
VOLC_ACCESS_KEY=你的VOLC_ACCESS_KEY
VOLC_SECRET_KEY=你的VOLC_SECRET_KEY
VOLC_MODEL_ENDPOINT=doubao-pro-32k
THIRD_PARTY_API_KEY=你的第三方API密钥
THIRD_PARTY_API_URL=https://api.example.com
```

如果你没有 **VOLC_ACCESS_KEY / VOLC_SECRET_KEY**，系统会自动使用规则引擎解读（不调用模型）。

---

## 数据口径说明（重要）

目前使用 **BaoStock** 数据接口：

- ROE：使用 `dupontROE`
- 毛利率：使用 `gpMargin`
- 净利润：`netProfit`
- 自由现金流（FCF）：**估算** = `净利润 × CFOToNP`

### 第三方交易API数据

- 价格、涨跌幅、成交量等实时数据

> BaoStock 不提供 Capex 明细，因此 FCF 为近似值。如需精准 FCF，建议改用 AkShare 或补充 Capex 数据源。

---

## 常见问题

**1. 图表数据为 0？**
- 请删除缓存文件 `finance.db`，然后刷新页面重新分析。

**2. 提示"仅检测到 API KEY（无 AK/SK）"？**
- 说明未配置 VOLC_ACCESS_KEY/VOLC_SECRET_KEY，模型解读将关闭，改用规则引擎。

**3. 为什么净利润和自由现金流差异大？**
- BaoStock 的 FCF 是估算值，建议接入 Capex 后再精算。

---

## 单测

```bash
python -m unittest tests/test_data_provider.py
```

支持指定股票：

```bash
STOCK_TEST_SYMBOLS=600519,600036 python -m unittest tests/test_data_provider.py
```

---

## 免责声明

本项目仅为学习与研究用途，不构成投资建议。
