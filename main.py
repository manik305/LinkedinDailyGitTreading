"""Unified entrypoint for the Autonomous Open-Source Spotlight Agent.

Supports both CLI pipeline execution and FastAPI server mode.
"""

import sys
import asyncio
import logging
import uvicorn

from src.config import get_settings
from src.agent_graph import SpotlightWorkflow
from src.db import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("main")


async def run_cli_pipeline() -> None:
    """Execute the daily spotlight workflow in CLI / GitHub Actions headless mode."""
    settings = get_settings()
    db = Database(settings.DATABASE_PATH)

    logger.info("Initializing Daily Spotlight Pipeline...")
    logger.info("Configured EURI Model: %s", settings.EURI_MODEL)
    logger.info("Max Tokens: %d | Temperature: %.2f", settings.EURI_MAX_TOKENS, settings.EURI_TEMPERATURE)

    if db.has_posted_today():
        logger.info("🛑 Daily limit enforced: A spotlight post has already been published today.")
        print("Daily quota met (1 post per day). Exiting.")
        return

    workflow = SpotlightWorkflow(settings)
    initial_state = {
        "trending_candidates": [],
        "current_index": 0,
        "selected_repo": None,
        "readme_content": None,
        "generated_draft": None,
        "telegram_message_id": None,
        "approval_status": None,
        "linkedin_post_urn": None,
        "error_message": None,
    }

    final_state = await workflow.graph.ainvoke(initial_state)

    status = final_state.get("approval_status")
    selected_repo = final_state.get("selected_repo", {}).get("full_name") if final_state.get("selected_repo") else None

    logger.info("Workflow finished with status: %s (Repo: %s)", status, selected_repo)
    if final_state.get("generated_draft"):
        print("\n" + "=" * 60)
        print("GENERATED LINKEDIN POST DRAFT:")
        print("=" * 60)
        print(final_state.get("generated_draft"))
        print("=" * 60 + "\n")


def start_server() -> None:
    """Launch the FastAPI server via Uvicorn."""
    settings = get_settings()
    logger.info("Starting FastAPI server at http://%s:%d", settings.SERVER_HOST, settings.SERVER_PORT)
    uvicorn.run(
        "src.api:app",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=True,
    )


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("run", "daily", "cli"):
        asyncio.run(run_cli_pipeline())
    else:
        start_server()
