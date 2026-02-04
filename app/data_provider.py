import datetime
import baostock as bs
import threading
import logging
import pandas as pd
from app.database import get_cached_data, save_to_cache

LOGGER = logging.getLogger(__name__)


# --- Helpers ---
def format_stock_code(symbol: str) -> str:
    """Ensures stock code has prefix (sh./sz.) for Baostock."""
    lower = symbol.lower()
    if lower.startswith(("sh.", "sz.")):
        return lower

    if symbol.startswith("6"):
        return f"sh.{symbol}"
    elif symbol.startswith(("0", "3")):
        return f"sz.{symbol}"
    return lower


# --- Core Fetching Logic ---


_LOGIN_LOCK = threading.Lock()
_LOGGED_IN = False


def _login():
    global _LOGGED_IN
    if _LOGGED_IN:
        LOGGER.debug("Baostock already logged in")
        return
    with _LOGIN_LOCK:
        if _LOGGED_IN:
            return
        LOGGER.info("Logging in to Baostock")
        lg = bs.login()
        if lg.error_code != "0":
            LOGGER.error("Baostock login failed: %s %s", lg.error_code, lg.error_msg)
            raise RuntimeError(f"baostock login failed: {lg.error_code} {lg.error_msg}")
        _LOGGED_IN = True
        LOGGER.info("Baostock login succeeded")


def _logout(force: bool = False):
    global _LOGGED_IN
    if not force:
        return
    try:
        LOGGER.info("Logging out from Baostock (force=%s)", force)
        bs.logout()
    finally:
        _LOGGED_IN = False


def _collect_rows(result):
    rows = []
    while result.error_code == "0" and result.next():
        rows.append(result.get_row_data())
    if result.error_code != "0":
        LOGGER.warning("Baostock query error: %s %s", result.error_code, result.error_msg)
    return rows


def _query_quarterly(report_func, code: str, years: int = 5):
    today = datetime.date.today()
    start_year = today.year - years + 1
    data = []
    LOGGER.info("Querying quarterly data for %s (%s years)", code, years)
    for y in range(start_year, today.year + 1):
        for q in (1, 2, 3, 4):
            rs = report_func(code=code, year=y, quarter=q)
            if rs.error_code != "0":
                LOGGER.warning(
                    "Quarterly query failed for %s Y%sQ%s: %s %s",
                    code,
                    y,
                    q,
                    rs.error_code,
                    rs.error_msg,
                )
                continue
            rows = _collect_rows(rs)
            if rows:
                df = pd.DataFrame(rows, columns=rs.fields)
                data.append(df)
    return pd.concat(data, ignore_index=True) if data else pd.DataFrame()


def get_company_name(symbol: str) -> str:
    f_symbol = format_stock_code(symbol)
    cache_key = f"{f_symbol}_company_name"
    LOGGER.info("Fetching company name for %s", f_symbol)
    cached = get_cached_data(cache_key, max_age_days=30)
    if cached:
        LOGGER.info("Using cached company name for %s", f_symbol)
        return cached.get("name", "")

    try:
        _login()
        rs = bs.query_stock_basic(code=f_symbol)
        rows = _collect_rows(rs)
        if rows:
            df = pd.DataFrame(rows, columns=rs.fields)
            name = df.iloc[0].get("code_name", "")
            save_to_cache(cache_key, {"name": name})
            return name
    except Exception:
        LOGGER.exception("Failed to fetch company name for %s", f_symbol)
        return ""
    finally:
        # keep session to avoid frequent login/logout
        pass
    return ""


def fetch_financial_report(symbol: str, report_type: str):
    """
    Fetches specific report type from EastMoney via AkShare.
    report_type: 'cash_flow', 'income', 'balance'
    """
    f_symbol = format_stock_code(symbol)
    cache_key = f"{f_symbol}_{report_type}_report"
    LOGGER.info("Fetching %s report for %s", report_type, f_symbol)

    # Financial reports don't change daily, cache for 7 days
    cached = get_cached_data(cache_key, max_age_days=7)
    if cached:
        LOGGER.info("Using cached %s report for %s", report_type, f_symbol)
        return pd.DataFrame(cached)

    try:
        _login()
        if report_type == "cash_flow":
            df = _query_quarterly(bs.query_cash_flow_data, f_symbol, years=5)
        elif report_type == "income":
            df = _query_quarterly(bs.query_profit_data, f_symbol, years=5)
        elif report_type == "balance":
            df = _query_quarterly(bs.query_dupont_data, f_symbol, years=5)
        else:
            LOGGER.warning("Unknown report type requested: %s", report_type)
            return pd.DataFrame()

        if not df.empty:
            save_to_cache(cache_key, df.to_dict(orient="records"))
            LOGGER.info(
                "Saved %s report for %s with %s rows",
                report_type,
                f_symbol,
                len(df),
            )
        else:
            LOGGER.warning("Empty %s report for %s", report_type, f_symbol)
        return df
    except Exception:
        LOGGER.exception("Error fetching %s for %s", report_type, f_symbol)
        return pd.DataFrame()
    finally:
        # keep session to avoid frequent login/logout
        pass


# --- Buffett Metrics Calculation ---


def get_buffett_metrics(symbol: str, annual_only: bool = True):
    """
    Aggregates financial data to produce Buffett-style metrics.
    Returns a dictionary structure suitable for visualization.
    """
    LOGGER.info("Calculating Buffett metrics for %s (annual_only=%s)", symbol, annual_only)
    cash_flow_df = fetch_financial_report(symbol, "cash_flow")
    income_df = fetch_financial_report(symbol, "income")
    balance_df = fetch_financial_report(symbol, "balance")

    if cash_flow_df.empty or income_df.empty or balance_df.empty:
        LOGGER.warning(
            "Missing data for %s: cash_flow=%s income=%s balance=%s",
            symbol,
            "missing" if cash_flow_df.empty else "present",
            "missing" if income_df.empty else "present",
            "missing" if balance_df.empty else "present",
        )
        return {"error": "Could not fetch complete financial data."}

    def process_df(df):
        date_cols = ["statDate", "pubDate", "reportDate", "REPORT_DATE"]
        for col in date_cols:
            if col in df.columns:
                df["date"] = pd.to_datetime(df[col])
                break
        return df

    def find_col_by_keywords(row, keyword_sets):
        cols = list(row.index)
        for keywords in keyword_sets:
            for col in cols:
                if all(k in col for k in keywords):
                    return col
        return None

    def get_col_value(row, exact_candidates, keyword_sets=None):
        for col in exact_candidates:
            if col in row:
                return row.get(col)
        if keyword_sets:
            fuzzy_col = find_col_by_keywords(row, keyword_sets)
            if fuzzy_col:
                return row.get(fuzzy_col)
        return None

    def safe_float(val):
        if val is None:
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        try:
            text = str(val).replace(",", "").strip()
            if text in {"--", "", "None", "nan"}:
                return 0.0
            return float(text)
        except Exception:
            return 0.0

    cf = process_df(cash_flow_df)
    inc = process_df(income_df)
    bal = process_df(balance_df)

    if annual_only:
        cf = cf[cf["date"].dt.month.eq(12) & cf["date"].dt.day.eq(31)]
        inc = inc[inc["date"].dt.month.eq(12) & inc["date"].dt.day.eq(31)]
        bal = bal[bal["date"].dt.month.eq(12) & bal["date"].dt.day.eq(31)]

    # Filter for Annual Reports Only (Month == 12) for long term trends?
    # Or TTM? For MVP, let's stick to Reporting Periods as returned (usually mixed).
    # Ideally filter for '12-31' for cleaner Year-on-Year comparison.

    # Extract Series
    analysis_data = []

    # We navigate dates present in Income Statement (usually the anchor)
    dates = inc["date"].tolist()

    for d in dates:
        d_str = d.strftime("%Y-%m-%d")

        # Get rows for this date
        inc_row = inc[inc["date"] == d].iloc[0]
        cf_row = cf[cf["date"] == d]
        bal_row = bal[bal["date"] == d]

        if cf_row.empty or bal_row.empty:
            LOGGER.debug("Skipping %s because cash flow or balance row missing", d_str)
            continue

        cf_row = cf_row.iloc[0]
        bal_row = bal_row.iloc[0]

        # Metric 1: ROE = Net Income / Equity
        # 归属于母公司所有者的净利润
        # 所有者权益合计
        try:
            net_income = safe_float(
                get_col_value(
                    inc_row,
                    ["netProfit", "netProfit".upper()],
                    keyword_sets=[["净利润"]],
                )
            )

            roe = safe_float(
                get_col_value(
                    bal_row,
                    ["dupontROE", "roeAvg"],
                    keyword_sets=[["ROE"]],
                )
            )
            if 0 < roe <= 1:
                roe = roe * 100

            # Metric 2: Gross Margin = (Revenue - Cost) / Revenue
            revenue = safe_float(
                get_col_value(
                    inc_row,
                    ["MBRevenue", "营业收入"],
                    keyword_sets=[["营业", "收入"], ["主营营业收入"]],
                )
            )
            gross_margin = safe_float(
                get_col_value(
                    inc_row,
                    ["gpMargin"],
                    keyword_sets=[["毛利率"], ["毛利"]],
                )
            )
            if 0 < gross_margin <= 1:
                gross_margin = gross_margin * 100

            # Metric 3: Free Cash Flow
            cfo_to_np = safe_float(
                get_col_value(
                    cf_row,
                    ["CFOToNP"],
                    keyword_sets=[["经营性现金净流量", "净利润"], ["CFOToNP"]],
                )
            )
            ocf = net_income * cfo_to_np if cfo_to_np else 0.0
            capex = 0.0
            fcf = ocf

            item = {
                "date": d_str,
                "roe": round(roe, 2),
                "gross_margin": round(gross_margin, 2),
                "revenue": round(revenue, 2),
                "net_income": round(net_income, 2),
                "fcf": round(fcf, 2),
                "ocf": round(ocf, 2),
                "capex": round(capex, 2),
            }
            analysis_data.append(item)

        except Exception:
            LOGGER.exception("Failed to compute metrics for %s on %s", symbol, d_str)
            continue

    # Sort by date ascending
    analysis_data.sort(key=lambda x: x["date"])

    company_name = get_company_name(symbol)
    LOGGER.info("Metrics ready for %s with %s rows", symbol, len(analysis_data))
    return {"symbol": symbol, "company_name": company_name, "metrics": analysis_data}


def get_current_valuation(symbol: str):
    """
    Get current PB/PE etc.
    """
    # For MVP, just return a dummy or fetch real time snapshot
    # ak.stock_zh_a_spot_em() is heavy.
    # Maybe specific one?
    return {"pe_ttm": 30.5, "pe_percentile": 20}  # Mock for MVP speed
