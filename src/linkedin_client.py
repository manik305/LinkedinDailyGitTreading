"""LinkedIn REST API client for publishing UGC posts."""

import logging
from typing import Optional
import httpx

from src.config import Settings

logger = logging.getLogger(__name__)


class LinkedInClient:
    """Client for publishing technical spotlight posts to LinkedIn."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.access_token = settings.LINKEDIN_ACCESS_TOKEN
        self.author_urn = settings.LINKEDIN_PERSON_URN

    async def publish_post(self, post_text: str) -> Optional[str]:
        """Publish text post to LinkedIn Community Management API and return post URN."""
        if not self.access_token or not self.author_urn:
            logger.warning("LinkedIn access token or author URN not configured. Simulating post.")
            return f"urn:li:simulated:{int(httpx._utils.to_str(b'123456789')) if hasattr(httpx._utils, 'to_str') else 'mock_urn_123'}"

        url = "https://api.linkedin.com/v2/ugcPosts"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        payload = {
            "author": self.author_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": post_text
                    },
                    "shareMediaCategory": "NONE"
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code in (200, 201):
                    data = response.json()
                    post_id = data.get("id") or response.headers.get("x-restli-id") or "urn:li:ugcPost:published"
                    logger.info("LinkedIn post successfully published! URN: %s", post_id)
                    return post_id
                else:
                    logger.error("LinkedIn publish failed with status %d: %s", response.status_code, response.text)
        except Exception as exc:
            logger.error("Exception during LinkedIn publishing: %s", exc)

        return None
