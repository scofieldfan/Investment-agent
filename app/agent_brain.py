import os
import logging
from typing import Annotated
from veadk import Agent, Runner
from dotenv import load_dotenv

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_ROOT)
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

from app.data_provider import get_buffett_metrics

LOGGER = logging.getLogger(__name__)

# Wrapper for the tool to be friendly to the Agent
def fetch_buffett_data(
    symbol: Annotated[str, "The stock symbol, e.g., '600519'"],
) -> str:
    """
    Retrieves calculated financial metrics (ROE, FCF, Gross Margin) for a given stock.
    Useful for analyzing financial health and durability (Moat).
    """
    data = get_buffett_metrics(symbol)
    if "error" in data:
        LOGGER.warning("Agent data fetch failed for %s: %s", symbol, data["error"])
        return f"Error: {data['error']}"

    # Summarize specifically for the LLM to reduce token usage if data is huge
    # We pass the full metrics list so it can see the trend
    return str(data)


def get_agent():
    api_key = os.getenv("ARK_API_KEY")
    model_endpoint = os.getenv("VOLC_MODEL_ENDPOINT")

    if not api_key:
        LOGGER.error("ARK_API_KEY missing; cannot initialize agent")
        raise ValueError("ARK_API_KEY not found in .env")

    # Initialize Agent
    LOGGER.info("Initializing Agent with model endpoint %s", model_endpoint)
    agent = Agent(
        name="BuffettAnalyst",
        description="A value investing assistant inspired by Warren Buffett.",
        instruction=(
            "You are an expert value investor (Buffett style). "
            "Your goal is to analyze companies based on their 'Moat' (ROE, Gross Margin) "
            "and 'Financial Engine' (Free Cash Flow). "
            "When asked about a stock, use the 'fetch_buffett_data' tool to get the content. "
            "Analyze the TRENDS. Is ROE stable > 15%? Is Free Cash Flow growing? "
            "Ignore short-term price fluctuations. Focus on the business quality."
            "Output your analysis in Markdown format."
        ),
        model_name=model_endpoint,
        tools=[fetch_buffett_data],
    )

    return agent


def run_agent_analysis(query: str):
    """
    Simple synchronous wrapper to run the agent for the Streamlit app.
    Streamlit is sync by default, but veadk is async.
    """
    import asyncio

    agent = get_agent()
    runner = Runner(agent=agent, app_name="investment_dashboard")
    LOGGER.info("Running agent analysis query")

    async def _run():
        session = await runner.short_term_memory.create_session(
            app_name="investment_dashboard",
            user_id="default_user",
        )
        LOGGER.info("Agent session created: %s", session.id)
        response = await runner.run(
            session_id=session.id, user_id="default_user", query=query
        )
        LOGGER.info("Agent response received")
        return response

    return asyncio.run(_run())
