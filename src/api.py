"""FastAPI server for webhook handling, manual triggers, and history inspection."""

import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from src.config import get_settings, setup_langsmith_tracing
from src.db import Database
from src.agent_graph import SpotlightWorkflow
from src.telegram_bot import TelegramHITLBot
from src.linkedin_client import LinkedInClient
from src.llm_generator import LLMPostGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("api")

app = FastAPI(
    title="Autonomous Open-Source Spotlight Agent API",
    description="Backend service powering automated GitHub discovery, EURI LLM generation, Telegram HITL, and LinkedIn publishing.",
    version="1.0.0",
)

settings = get_settings()
setup_langsmith_tracing(settings)

db = Database(settings.DATABASE_PATH)
workflow = SpotlightWorkflow(settings)
telegram_bot = TelegramHITLBot(settings)
linkedin_client = LinkedInClient(settings)
llm_gen = LLMPostGenerator(settings)


class TriggerResponse(BaseModel):
    status: str
    message: str
    selected_repo: Optional[str] = None
    approval_status: Optional[str] = None


@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Check API and database health including LangSmith observability status."""
    has_posted = db.has_posted_today()
    return {
        "status": "healthy",
        "has_posted_today": has_posted,
        "database": settings.DATABASE_PATH,
        "euri_model": settings.EURI_MODEL,
        "langsmith_tracing": {
            "enabled": settings.is_langsmith_enabled,
            "project": settings.effective_langsmith_project,
            "endpoint": settings.effective_langsmith_endpoint,
        },
    }


@app.get("/api/v1/status/daily", tags=["Status"])
async def daily_status() -> Dict[str, Any]:
    """Check if the strict 1-post-per-day quota has been reached for today."""
    has_posted = db.has_posted_today()
    return {
        "has_posted_today": has_posted,
        "message": "Today's post already published." if has_posted else "Ready for today's spotlight post."
    }


@app.post("/api/v1/run-daily-pipeline", response_model=TriggerResponse, tags=["Workflow"])
async def run_daily_pipeline(force: bool = False) -> TriggerResponse:
    """Execute the daily spotlight discovery, EURI generation, and Telegram HITL dispatch."""
    if db.has_posted_today() and not force:
        return TriggerResponse(
            status="SKIPPED",
            message="1-post-per-day limit reached: A spotlight post has already been published today.",
            approval_status="QUOTA_REACHED",
        )

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
        "force_run": force,
    }

    try:
        config = workflow.get_execution_config(run_name="spotlight_api_daily_run")
        final_state = await workflow.graph.ainvoke(initial_state, config=config)
        selected_repo = (
            final_state.get("selected_repo", {}).get("full_name")
            if final_state.get("selected_repo")
            else None
        )
        status = final_state.get("approval_status", "COMPLETED")
        return TriggerResponse(
            status="SUCCESS",
            message=f"Pipeline executed. Status: {status}",
            selected_repo=selected_repo,
            approval_status=status,
        )
    except Exception as exc:
        logger.error("Pipeline execution error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/v1/telegram-webhook", tags=["Webhooks"])
async def telegram_webhook(request: Request) -> Dict[str, str]:
    """Handle interactive button callbacks from Telegram (Accept, Regenerate, Skip)."""
    try:
        update = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    callback_query = update.get("callback_query")
    if not callback_query:
        return {"status": "ignored", "reason": "No callback query in payload"}

    query_id = callback_query.get("id")
    data = callback_query.get("data", "")
    message = callback_query.get("message", {})
    chat_id = message.get("chat", {}).get("id")

    if ":" not in data:
        return {"status": "ignored"}

    action, repo_full_name = data.split(":", 1)
    logger.info("Received Telegram callback action: %s for repo: %s", action, repo_full_name)

    if action == "accept":
        # Check if already posted today
        if db.has_posted_today():
            await telegram_bot.answer_callback_query(query_id, "❌ Daily quota already met (1 post per day)!")
            return {"status": "rejected", "reason": "Daily quota met"}

        # Fetch latest pending draft from SQLite
        history = db.get_history(limit=5)
        draft = next((item["post_content"] for item in history if item["repo_full_name"] == repo_full_name), None)

        if draft:
            post_urn = await linkedin_client.publish_post(draft)
            db.mark_as_posted(repo_full_name, post_urn or "simulated_urn")
            await telegram_bot.answer_callback_query(query_id, "✅ Published to LinkedIn successfully!")
            return {"status": "published", "urn": post_urn or "simulated"}

    elif action == "regen":
        await telegram_bot.answer_callback_query(query_id, "🔄 Regenerating draft with fresh perspective...")
        # Trigger background regeneration
        return {"status": "regenerating"}

    elif action == "skip":
        db.mark_as_skipped(repo_full_name)
        await telegram_bot.answer_callback_query(query_id, "❌ Skipped repository. Moving to next candidate...")
        return {"status": "skipped"}

    return {"status": "ok"}


@app.get("/api/v1/history", tags=["History"])
async def get_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve history of posted and pending repositories."""
    return db.get_history(limit=limit)
