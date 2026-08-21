"""LLM Post Generation service using EURI OpenAI-compatible API with human-first prompts."""

import logging
from typing import Any, Dict, Optional
from openai import OpenAI

from src.config import Settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a senior software architect and open-source practitioner writing an authentic, insightful LinkedIn post.

Your goal is to spotlight a remarkable open-source project so that it reads 100% like a genuine, thoughtful post written by a real human engineer—NOT an AI-generated template.

STRICT WRITING RULES & GUARDRAILS:
1. ZERO AI CLICHÉS: Never use words or phrases like "In the fast-paced world", "Game-changer", "Delve", "Tapestry", "Unleash", "Dive into", "Supercharge", "Look no further", "Revolutionize".
2. PRACTITIONER FIRST-PERSON VOICE: Write naturally from experience (e.g., "I've been looking into how...", "What caught my eye in their architecture is...", "If you've ever dealt with X, this makes total sense").
3. CONCRETE ARCHITECTURAL VALUE: Focus on engineering trade-offs, performance gains, memory efficiency, design patterns, and why this project solves a real pain point.
4. ZERO HALLUCINATION: Only state facts, benchmarks, and features explicitly present in the provided README and repository metadata. Do not invent features.
5. CLEAN MOBILE-FRIENDLY FORMATTING:
   - High-impact, engaging hook (1-2 lines)
   - The friction/problem engineers face (2-3 lines)
   - Bullet points for core architectural highlights & capabilities
   - Technical stack / runtime summary
   - Thoughtful, genuine question to spark comments among engineers
   - Mention: "🔗 Dropping the GitHub link in the first comment 👇"
   - 4-5 relevant hashtags (e.g., #SoftwareEngineering #OpenSource #DevCommunity #SystemDesign)
"""


class LLMPostGenerator:
    """Generates authentic LinkedIn posts using the EURI inference endpoint."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(
            api_key=settings.EURI_API_KEY,
            base_url=settings.EURI_BASE_URL,
        )

    def generate_spotlight_post(
        self,
        repo_metadata: Dict[str, Any],
        readme_content: str,
        regeneration_feedback: Optional[str] = None,
    ) -> str:
        """Synthesize a human-like LinkedIn post from repository context."""
        topics_str = ", ".join(repo_metadata.get("topics", [])) or "None listed"
        user_prompt = f"""Write a compelling, human-crafted LinkedIn spotlight post for the following open-source project:

Repository Name: {repo_metadata.get('full_name')}
Stars: {repo_metadata.get('stargazers_count', 'N/A'):,}
Primary Language: {repo_metadata.get('language', 'General')}
Topics: {topics_str}
Short Description: {repo_metadata.get('description', '')}

README Context:
\"\"\"
{readme_content}
\"\"\"
"""
        if regeneration_feedback:
            user_prompt += f"\n\nAdjustments requested for this regeneration: {regeneration_feedback}"

        try:
            logger.info("Calling EURI API with model: %s", self.settings.EURI_MODEL)
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
            logger.error("Error generating post via EURI LLM: %s", exc)
            # Fallback human-formatted post if API key is not yet set or unreachable
            return self._build_fallback_post(repo_metadata)

    def _build_fallback_post(self, repo: Dict[str, Any]) -> str:
        """Create a structured draft in case of LLM connectivity failure."""
        name = repo.get("name", "the project")
        full_name = repo.get("full_name", "")
        desc = repo.get("description", "A powerful modern developer tool.")
        lang = repo.get("language", "Software")
        stars = repo.get("stargazers_count", 0)

        return (
            f"I've been looking into how {name} approaches modern {lang} workflows—and their architecture is worth checking out.\n\n"
            f"Problem it solves:\n"
            f"{desc}\n\n"
            f"Why it stands out:\n"
            f"• Crosses over {stars:,} GitHub stars with active community adoption\n"
            f"• Purpose-built for developer velocity and minimal runtime overhead\n"
            f"• Clean modular codebase with transparent configuration\n\n"
            f"Under the hood: Built primarily in {lang}.\n\n"
            f"Has anyone here experimented with {name} in production yet? What has your experience been?\n\n"
            f"🔗 Dropping the GitHub repo link in the first comment 👇\n"
            f"#SoftwareEngineering #OpenSource #DevCommunity #{lang.replace(' ', '')}"
        )
