"""LLM Post Generation service using EURI OpenAI-compatible API with LangSmith observability."""

import logging
from typing import Any, Callable, Dict, Optional
from openai import OpenAI

from src.config import Settings, setup_langsmith_tracing

logger = logging.getLogger(__name__)

# Optional LangSmith imports with graceful no-op fallbacks
try:
    from langsmith import traceable
    from langsmith.wrappers import wrap_openai
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False

    def traceable(*args: Any, **kwargs: Any) -> Callable[[Any], Any]:
        """No-op traceable decorator fallback when langsmith is not installed."""
        def decorator(func: Callable[[Any], Any]) -> Callable[[Any], Any]:
            return func
        return decorator

    def wrap_openai(client: Any) -> Any:
        """No-op OpenAI client wrapper fallback."""
        return client


SYSTEM_PROMPT = """You are a seasoned Principal Software Architect and open-source evangelist writing an in-depth, authentic LinkedIn technical breakdown.

Your goal is to spotlight a remarkable open-source project in a deeply thoughtful, human practitioner's voice. The post must provide immediate architectural clarity, explain the developer pain point it solves, and illustrate how engineering teams can directly benefit from adopting it.

STRICT WRITING RULES & TONE GUARDRAILS:
1. ZERO AI CLICHÉS: Strictly forbid phrases like "In the fast-paced world", "Game-changer", "Delve into", "Tapestry", "Unleash", "Dive deep", "Supercharge", "Look no further", "Revolutionize", "In today's landscape".
2. PRACTITIONER FIRST-PERSON PERSPECTIVE: Write naturally as an engineer who evaluated the codebase and architecture (e.g., "I've been analyzing how...", "What caught my eye in their architecture is...", "If your team has ever struggled with X, this makes total sense").
3. CONCRETE DEVELOPER VALUE & ARCHITECTURAL SUBSTANCE:
   - Clearly articulate the friction/pain point developers face without this tool.
   - Explain the architectural mechanism (e.g., zero-copy parsing, AST transformations, declarative configs, concurrency models).
   - Detail how this directly saves time, improves reliability, or reduces complexity for individual devs and teams.
4. ZERO HALLUCINATION: All technical claims, benchmark numbers, features, and stack details must be grounded strictly in the provided README and repository metadata.
5. STRUCTURED, HIGH-READABILITY FORMAT:
   - 🎯 Engaging Hook (1-2 lines identifying the problem space)
   - ⚠️ The Core Engineering Friction (Why existing setups are painful or fragile)
   - 💡 How [Project Name] Solves It & Directly Helps Developers (Detailed breakdown of capabilities, architectural highlights, and team impact)
   - 🛠️ Under the Hood (Tech stack, runtime characteristics, key integrations)
   - 📌 When to Reach for It (Ideal team scenarios or production workflows)
   - 💬 Thoughtful Discussion Prompt (Specific technical question for the community)
   - 🔗 "Dropping the GitHub repo link in the first comment 👇"
   - 🏷️ 4-5 relevant hashtags (e.g., #SoftwareEngineering #OpenSource #DevOps #SystemDesign)
"""


class LLMPostGenerator:
    """Generates authentic LinkedIn posts using the EURI inference endpoint with LangSmith tracing."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        setup_langsmith_tracing(settings)

        base_client = OpenAI(
            api_key=settings.EURI_API_KEY,
            base_url=settings.EURI_BASE_URL,
        )

        if settings.is_langsmith_enabled and LANGSMITH_AVAILABLE:
            try:
                self.client = wrap_openai(base_client)
                logger.info("LangSmith OpenAI wrapper successfully attached to EURI client.")
            except Exception as wrap_err:
                logger.warning("Could not wrap OpenAI client with LangSmith: %s", wrap_err)
                self.client = base_client
        else:
            self.client = base_client

    @traceable(
        name="generate_spotlight_post",
        run_type="chain",
        tags=["euri-llm", "linkedin-post-generator"],
    )
    def generate_spotlight_post(
        self,
        repo_metadata: Dict[str, Any],
        readme_content: str,
        regeneration_feedback: Optional[str] = None,
    ) -> str:
        """Synthesize an authentic, comprehensive LinkedIn technical post from repository context."""
        repo_name = repo_metadata.get("full_name", "Unknown")
        topics_str = ", ".join(repo_metadata.get("topics", [])) or "None listed"
        user_prompt = f"""Craft an insightful, comprehensive LinkedIn spotlight breakdown for the following open-source project:

Repository: {repo_name}
Stars: {repo_metadata.get('stargazers_count', 'N/A'):,} | Forks: {repo_metadata.get('forks_count', 'N/A'):,}
Primary Language: {repo_metadata.get('language', 'General')}
Topics: {topics_str}
Description: {repo_metadata.get('description', '')}

README Documentation:
\"\"\"
{readme_content}
\"\"\"

Focus on:
1. What friction or bottleneck engineers face in this problem domain.
2. The specific architectural solution and mechanism this project provides.
3. Concrete ways it helps individual developers and teams streamline workflows.
4. Stack summary and practical adoption guidance.
"""
        if regeneration_feedback:
            user_prompt += f"\n\nAdditional adjustments requested: {regeneration_feedback}"

        try:
            logger.info("Calling EURI API with model: %s for repo: %s", self.settings.EURI_MODEL, repo_name)
            response = self.client.chat.completions.create(
                model=self.settings.EURI_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=self.settings.EURI_MAX_TOKENS,
                temperature=self.settings.EURI_TEMPERATURE,
            )
            post_text = response.choices[0].message.content.strip()
            return post_text
        except Exception as exc:
            logger.error("Error generating post via EURI LLM for %s: %s", repo_name, exc)
            # Fallback human-formatted post if API key is not yet set or unreachable
            return self._build_fallback_post(repo_metadata)

    @traceable(
        name="fallback_post_generator",
        run_type="parser",
        tags=["fallback-template"],
    )
    def _build_fallback_post(self, repo: Dict[str, Any]) -> str:
        """Create an in-depth structured draft in case of LLM connectivity failure."""
        name = repo.get("name", "the project")
        full_name = repo.get("full_name", "")
        desc = repo.get("description", "A powerful modern developer tool designed for scale.")
        lang = repo.get("language", "Software")
        stars = repo.get("stargazers_count", 0)
        topics = repo.get("topics", [])
        topic_preview = ", ".join(topics[:3]) if topics else lang

        return (
            f"I've been analyzing how {name} tackles modern {lang} development—and its architectural design solves a very real friction point for engineering teams.\n\n"
            f"The Friction Most Teams Face:\n"
            f"As applications scale, managing {topic_preview} workflows often leads to brittle pipelines, excessive boilerplate, and slow feedback loops during local iteration.\n\n"
            f"How {name} Directly Helps Developers & Teams:\n"
            f"• Purpose-Built Efficiency: {desc}\n"
            f"• Streamlined DX: Provides intuitive abstractions that remove tedious configuration and cut down cycle time\n"
            f"• Production Resilience: Proven adoption across {stars:,}+ GitHub stars with active community maintenance\n"
            f"• Modular Architecture: Designed to drop into existing CI/CD and production stacks with minimal friction\n\n"
            f"Under the Hood:\n"
            f"Engineered primarily in {lang} with lightweight dependencies and transparent configuration.\n\n"
            f"When to Reach for It:\n"
            f"If your team is looking to standardize {topic_preview} workflows without taking on heavyweight operational complexity, {name} is well worth evaluating.\n\n"
            f"Have you evaluated or deployed {name} in your organization? What was your biggest takeaway from its architecture?\n\n"
            f"🔗 Dropping the GitHub repo link in the first comment 👇\n"
            f"#SoftwareEngineering #OpenSource #DevCommunity #{lang.replace(' ', '')} #Architecture"
        )
