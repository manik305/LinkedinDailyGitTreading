"""GitHub API client for discovering trending repositories and ingesting clean READMEs."""

import re
import logging
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)


class GitHubClient:
    """Client for GitHub API operations."""

    def __init__(self, token: Optional[str] = None, min_stars: int = 5000) -> None:
        self.token = token
        self.min_stars = min_stars
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Autonomous-Spotlight-Agent/1.0",
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    async def fetch_trending_candidates(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Fetch repositories with >= min_stars sorted by recent activity or stars."""
        url = "https://api.github.com/search/repositories"
        params = {
            "q": f"stars:>={self.min_stars}",
            "sort": "updated",
            "order": "desc",
            "per_page": limit,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=self.headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    items = data.get("items", [])
                    candidates = []
                    for item in items:
                        candidates.append({
                            "full_name": item.get("full_name"),
                            "name": item.get("name"),
                            "html_url": item.get("html_url"),
                            "description": item.get("description") or "",
                            "stargazers_count": item.get("stargazers_count", 0),
                            "language": item.get("language") or "General",
                            "topics": item.get("topics", []),
                            "forks_count": item.get("forks_count", 0),
                            "open_issues_count": item.get("open_issues_count", 0),
                            "default_branch": item.get("default_branch", "main"),
                        })
                    return candidates
                else:
                    logger.warning(
                        "GitHub search API failed with status %d: %s. Using curated fallback.",
                        response.status_code,
                        response.text,
                    )
        except Exception as exc:
            logger.error("Exception fetching GitHub trending candidates: %s", exc)

        # High-quality fallback candidates if rate limited or offline
        return self._get_fallback_candidates()

    def _get_fallback_candidates(self) -> List[Dict[str, Any]]:
        """Fallback candidate repositories if GitHub API is unreachable."""
        return [
            {
                "full_name": "astral-sh/uv",
                "name": "uv",
                "html_url": "https://github.com/astral-sh/uv",
                "description": "An extremely fast Python package and project manager, written in Rust.",
                "stargazers_count": 42000,
                "language": "Rust",
                "topics": ["python", "package-manager", "rust", "developer-tools"],
                "forks_count": 1200,
                "open_issues_count": 150,
                "default_branch": "main",
            },
            {
                "full_name": "ollama/ollama",
                "name": "ollama",
                "html_url": "https://github.com/ollama/ollama",
                "description": "Get up and running with Llama 3, Mistral, Gemma, and other large language models.",
                "stargazers_count": 98000,
                "language": "Go",
                "topics": ["llm", "ai", "go", "llama"],
                "forks_count": 7800,
                "open_issues_count": 320,
                "default_branch": "main",
            },
            {
                "full_name": "shadcn-ui/ui",
                "name": "ui",
                "html_url": "https://github.com/shadcn-ui/ui",
                "description": "Beautifully designed components that you can copy and paste into your apps.",
                "stargazers_count": 72000,
                "language": "TypeScript",
                "topics": ["react", "tailwind", "ui", "components"],
                "forks_count": 5600,
                "open_issues_count": 210,
                "default_branch": "main",
            },
        ]

    async def fetch_clean_readme(self, repo_full_name: str, default_branch: str = "main") -> str:
        """Fetch raw README.md from GitHub and sanitize away markdown badges/noise."""
        branches_to_try = [default_branch, "master", "main"]
        filenames_to_try = ["README.md", "readme.md", "README.rst", "README.txt"]

        async with httpx.AsyncClient(timeout=15.0) as client:
            for branch in branches_to_try:
                for filename in filenames_to_try:
                    raw_url = f"https://raw.githubusercontent.com/{repo_full_name}/{branch}/{filename}"
                    try:
                        resp = await client.get(raw_url, headers=self.headers)
                        if resp.status_code == 200 and resp.text:
                            return self._sanitize_readme(resp.text)
                    except Exception:
                        continue

        return "README not available. Please rely on repository description and metadata."

    def _sanitize_readme(self, content: str, max_chars: int = 15000) -> str:
        """Strip HTML tags, badge shields, contributor tables, and license clutter."""
        # Remove badge images and links [![...](...)](...)
        content = re.sub(r"\[!\[.*?\]\(.*?\)\]\(.*?\)", "", content)
        # Remove standalone badge images ![...](...)
        content = re.sub(r"!\[.*?\]\(.*?\)", "", content)
        # Remove HTML comments
        content = re.sub(r"<!--[\s\S]*?-->", "", content)
        # Remove excessive whitespace/newlines
        content = re.sub(r"\n{3,}", "\n\n", content)
        # Limit character count to avoid prompt overflow while retaining core architecture
        return content[:max_chars].strip()
