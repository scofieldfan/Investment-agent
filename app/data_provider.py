import os
import sys
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from dotenv import load_dotenv
import requests

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

# Fetch第三方交易API数据
def fetch_third_party_stock_data(symbol: str) -> dict:
    """
    从第三方交易API获取股票数据（示例）
    实际使用时替换为真实的API endpoint
    """
    try:
        # 示例：使用某个免费股票API
        # TODO: 替换为实际的第三方交易API
        api_url = f"https://api.example.com/stock/{symbol}"
        response = requests.get(api_url, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return {"error": f"API返回错误: {response.status_code}"}
    except Exception as e:
        return {"error": f"请求失败: {str(e)}"}
