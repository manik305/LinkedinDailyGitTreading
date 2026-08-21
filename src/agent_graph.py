"""LangGraph state machine and workflow execution engine."""

import logging
from typing import Any, Dict, List, Optional, TypedDict
from langgraph.graph import StateGraph, END

from src.config import Settings, get_settings
from src.db import Database
from src.github_client import GitHubClient
from src.llm_generator import LLMPostGenerator
from src.telegram_bot import TelegramHITLBot
from src.linkedin_client import LinkedInClient

logger = logging.getLogger(__name__)


class AgentState(TypedDict):
    """Complete workflow state definition for the spotlight agent."""
    trending_candidates: List[Dict[str, Any]]
    current_index: int
    selected_repo: Optional[Dict[str, Any]]
    readme_content: Optional[str]
    generated_draft: Optional[str]
    telegram_message_id: Optional[int]
    approval_status: Optional[str]  # 'PENDING', 'APPROVED', 'REJECTED', 'REGENERATE', 'QUOTA_REACHED'
    linkedin_post_urn: Optional[str]
    error_message: Optional[str]


class SpotlightWorkflow:
    """Orchestrates the LangGraph agent workflow."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.db = Database(self.settings.DATABASE_PATH)
        self.github = GitHubClient(self.settings.GITHUB_TOKEN, self.settings.MIN_GITHUB_STARS)
        self.llm = LLMPostGenerator(self.settings)
        self.telegram = TelegramHITLBot(self.settings)
        self.linkedin = LinkedInClient(self.settings)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Construct the LangGraph StateGraph with nodes and conditional edges."""
        builder = StateGraph(AgentState)

        # Register nodes
        builder.add_node("fetch_trending", self.fetch_trending_node)
        builder.add_node("filter_and_validate", self.filter_and_validate_node)
        builder.add_node("ingest_context", self.ingest_context_node)
        builder.add_node("generate_post", self.generate_post_node)
        builder.add_node("dispatch_telegram", self.dispatch_telegram_node)
        builder.add_node("publish_linkedin", self.publish_linkedin_node)
        builder.add_node("persist_state", self.persist_state_node)

        # Set entrypoint
        builder.set_entry_point("fetch_trending")

        # Edges
        builder.add_edge("fetch_trending", "filter_and_validate")

        # Conditional Edge after validation
        builder.add_conditional_edges(
            "filter_and_validate",
            self._route_after_validation,
            {
                "quota_reached": END,
                "valid_repo": "ingest_context",
                "next_repo": "filter_and_validate",
                "no_candidates": END,
            }
        )

        builder.add_edge("ingest_context", "generate_post")
        builder.add_edge("generate_post", "dispatch_telegram")

        # Conditional Edge after Telegram HITL dispatch
        builder.add_conditional_edges(
            "dispatch_telegram",
            self._route_after_telegram,
            {
                "auto_publish": "publish_linkedin",
                "await_hitl": END,
                "regenerate": "generate_post",
                "skip": "filter_and_validate",
            }
        )

        builder.add_edge("publish_linkedin", "persist_state")
        builder.add_edge("persist_state", END)

        return builder.compile()

    # --- Node Implementations ---

    async def fetch_trending_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 1: Discover trending candidate repositories."""
        logger.info("Fetching trending GitHub repositories...")
        candidates = await self.github.fetch_trending_candidates()
        return {
            "trending_candidates": candidates,
            "current_index": 0,
            "selected_repo": None,
            "approval_status": "INITIALIZED",
        }

    async def filter_and_validate_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 2: Apply 1-post-per-day guard and deduplication against SQLite."""
        # 1. Enforce strict 1-post-per-day limit
        if self.db.has_posted_today():
            logger.info("Daily quota reached: A spotlight post has already been published today.")
            return {
                "approval_status": "QUOTA_REACHED",
                "error_message": "Daily quota met. Only 1 post allowed per day."
            }

        candidates = state.get("trending_candidates", [])
        idx = state.get("current_index", 0)

        while idx < len(candidates):
            candidate = candidates[idx]
            repo_name = candidate.get("full_name")
            stars = candidate.get("stargazers_count", 0)

            # Check stars and database deduplication
            if stars >= self.settings.MIN_GITHUB_STARS and not self.db.is_repo_processed(repo_name):
                logger.info("Selected new candidate repository: %s (⭐ %s)", repo_name, stars)
                return {
                    "selected_repo": candidate,
                    "current_index": idx,
                    "approval_status": "VALIDATED",
                }
            idx += 1

        logger.warning("No unposted candidate repositories found meeting criteria.")
        return {
            "selected_repo": None,
            "current_index": idx,
            "approval_status": "NO_CANDIDATES",
        }

    async def ingest_context_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 3: Fetch and sanitize repository README."""
        repo = state.get("selected_repo")
        if not repo:
            return {"error_message": "No selected repo for ingestion."}

        repo_name = repo.get("full_name")
        branch = repo.get("default_branch", "main")
        logger.info("Ingesting README for %s...", repo_name)
        readme = await self.github.fetch_clean_readme(repo_name, default_branch=branch)
        return {"readme_content": readme}

    async def generate_post_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 4: Synthesize human-sounding LinkedIn post using EURI LLM."""
        repo = state.get("selected_repo")
        readme = state.get("readme_content", "")
        if not repo:
            return {"error_message": "No repository selected for post generation."}

        logger.info("Generating human-crafted LinkedIn post for %s via EURI...", repo.get("full_name"))
        draft = self.llm.generate_spotlight_post(repo, readme)

        # Record draft as pending in database
        topics_str = ", ".join(repo.get("topics", []))
        self.db.record_pending_post(
            repo_full_name=repo.get("full_name"),
            repo_url=repo.get("html_url"),
            stars_count=repo.get("stargazers_count", 0),
            language=repo.get("language"),
            topics=topics_str,
            post_content=draft,
        )

        return {"generated_draft": draft, "approval_status": "PENDING"}

    async def dispatch_telegram_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 5: Send preview to Telegram chat for Human-In-The-Loop review."""
        repo = state.get("selected_repo")
        draft = state.get("generated_draft")

        if repo and draft:
            msg_id = await self.telegram.send_draft_for_approval(
                repo_full_name=repo.get("full_name"),
                repo_url=repo.get("html_url"),
                stars=repo.get("stargazers_count", 0),
                draft_content=draft,
            )
            return {"telegram_message_id": msg_id}
        return {}

    async def publish_linkedin_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 6: Publish post to LinkedIn."""
        draft = state.get("generated_draft")
        if not draft:
            return {"error_message": "No draft content to publish."}

        logger.info("Publishing post to LinkedIn...")
        post_urn = await self.linkedin.publish_post(draft)
        return {"linkedin_post_urn": post_urn, "approval_status": "POSTED"}

    async def persist_state_node(self, state: AgentState) -> Dict[str, Any]:
        """Node 7: Persist post confirmation and timestamp to SQLite."""
        repo = state.get("selected_repo")
        urn = state.get("linkedin_post_urn", "simulated_urn")
        if repo:
            logger.info("Persisting completed post record for %s to SQLite...", repo.get("full_name"))
            self.db.mark_as_posted(repo.get("full_name"), urn)
        return {}

    # --- Routing Helpers ---

    def _route_after_validation(self, state: AgentState) -> str:
        status = state.get("approval_status")
        if status == "QUOTA_REACHED":
            return "quota_reached"
        if status == "VALIDATED" and state.get("selected_repo"):
            return "valid_repo"
        if status == "NO_CANDIDATES":
            return "no_candidates"
        return "next_repo"

    def _route_after_telegram(self, state: AgentState) -> str:
        # In headless automated mode (without Telegram credentials), auto-publish or await hitl
        if not self.settings.TELEGRAM_BOT_TOKEN or not self.settings.TELEGRAM_CHAT_ID:
            logger.info("No Telegram HITL configured. Proceeding to direct LinkedIn publishing.")
            return "auto_publish"
        return "await_hitl"
