"""Telegram Bot Human-In-The-Loop (HITL) dispatcher."""

import logging
from typing import Any, Dict, Optional
import httpx

from src.config import Settings

logger = logging.getLogger(__name__)


class TelegramHITLBot:
    """Dispatches draft previews to Telegram and provides inline interaction."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.bot_token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID

    async def send_draft_for_approval(
        self,
        repo_full_name: str,
        repo_url: str,
        stars: int,
        draft_content: str,
    ) -> Optional[int]:
        """Send formatted draft post with inline keyboard buttons to Telegram chat."""
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram bot token or chat ID is missing. Skipping Telegram dispatch.")
            return None

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

        preview_text = (
            f"📢 *Daily Open-Source Spotlight Draft*\n"
            f"📦 *Repository:* `{repo_full_name}` (⭐ {stars:,})\n"
            f"🔗 *URL:* {repo_url}\n\n"
            f"────────────────────────\n"
            f"{draft_content}\n"
            f"────────────────────────\n\n"
            f"👇 *Select an action:*"
        )

        inline_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Accept & Post to LinkedIn", "callback_data": f"accept:{repo_full_name}"},
                ],
                [
                    {"text": "🔄 Regenerate Post", "callback_data": f"regen:{repo_full_name}"},
                    {"text": "❌ Skip Repo", "callback_data": f"skip:{repo_full_name}"},
                ],
            ]
        }

        payload = {
            "chat_id": self.chat_id,
            "text": preview_text,
            "reply_markup": inline_keyboard,
            "disable_web_page_preview": True,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    message_id = data.get("result", {}).get("message_id")
                    logger.info("Draft successfully sent to Telegram. Message ID: %s", message_id)
                    return message_id
                else:
                    logger.error("Failed to send Telegram message: %s", response.text)
        except Exception as exc:
            logger.error("Telegram API communication error: %s", exc)

        return None

    async def answer_callback_query(self, callback_query_id: str, text: str) -> None:
        """Acknowledge Telegram callback query."""
        if not self.bot_token:
            return

        url = f"https://api.telegram.org/bot{self.bot_token}/answerCallbackQuery"
        payload = {"callback_query_id": callback_query_id, "text": text}
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(url, json=payload)
        except Exception as exc:
            logger.error("Error answering callback query: %s", exc)
