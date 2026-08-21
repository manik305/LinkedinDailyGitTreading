"""SQLite persistence layer with 1-post-per-day cooldown and deduplication."""

import os
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any


class Database:
    """SQLite Database manager for tracking spotlighted repositories."""

    def __init__(self, db_path: str = "data/history.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self.init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and return a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        """Initialize database schema and required indexes."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS posted_repos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    repo_full_name TEXT UNIQUE NOT NULL,
                    repo_url TEXT NOT NULL,
                    stars_count INTEGER NOT NULL,
                    language TEXT,
                    topics TEXT,
                    post_content TEXT NOT NULL,
                    linkedin_post_urn TEXT,
                    status TEXT CHECK(status IN ('PENDING', 'POSTED', 'SKIPPED', 'REJECTED')) DEFAULT 'PENDING',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    posted_at TIMESTAMP
                );
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_repo_full_name ON posted_repos(repo_full_name);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_status ON posted_repos(status);"
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_posted_at ON posted_repos(posted_at);"
            )
            conn.commit()

    def has_posted_today(self) -> bool:
        """Enforce strict 1-post-per-day rule. Return True if a post was published today."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) as count 
                FROM posted_repos 
                WHERE date(posted_at) = date('now') AND status = 'POSTED';
                """
            )
            row = cursor.fetchone()
            return bool(row["count"] > 0) if row else False

    def is_repo_processed(self, repo_full_name: str) -> bool:
        """Check if a repository has already been spotlighted or processed."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM posted_repos WHERE repo_full_name = ?;",
                (repo_full_name,),
            )
            return cursor.fetchone() is not None

    def record_pending_post(
        self,
        repo_full_name: str,
        repo_url: str,
        stars_count: int,
        language: Optional[str],
        topics: str,
        post_content: str,
    ) -> int:
        """Insert or update a pending post draft."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO posted_repos (
                    repo_full_name, repo_url, stars_count, language, topics, post_content, status
                ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING')
                ON CONFLICT(repo_full_name) DO UPDATE SET
                    post_content = excluded.post_content,
                    status = 'PENDING';
                """,
                (repo_full_name, repo_url, stars_count, language, topics, post_content),
            )
            conn.commit()
            return cursor.lastrowid

    def mark_as_posted(self, repo_full_name: str, linkedin_post_urn: str) -> None:
        """Mark a repository post as successfully published to LinkedIn."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE posted_repos 
                SET status = 'POSTED', 
                    linkedin_post_urn = ?, 
                    posted_at = datetime('now')
                WHERE repo_full_name = ?;
                """,
                (linkedin_post_urn, repo_full_name),
            )
            conn.commit()

    def mark_as_skipped(self, repo_full_name: str) -> None:
        """Mark a repository as skipped."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE posted_repos SET status = 'SKIPPED' WHERE repo_full_name = ?;",
                (repo_full_name,),
            )
            conn.commit()

    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieve recent spotlight history."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, repo_full_name, repo_url, stars_count, language, 
                       post_content, linkedin_post_urn, status, created_at, posted_at
                FROM posted_repos
                ORDER BY created_at DESC
                LIMIT ?;
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
