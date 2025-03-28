from datetime import datetime
import logging
from pathlib import Path
from typing import List, Tuple, Optional

import psycopg2

from src.config import DB_CONFIG

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Database:
    def __init__(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cur = self.conn.cursor()
            self._create_tables()
            self._seed_data()
            logger.info("Database initialized successfully.")
        except Exception as e:
            logger.error(f"Error connecting to the database: {e}")
            raise

    def _execute_sql_script(self, script_path: str):
        """Execute an SQL script from a file."""
        try:
            with open(script_path, "r", encoding="utf-8") as f:
                sql = f.read()
            self.cur.execute(sql)
            self.conn.commit()
            logger.info(f"Executed SQL script: {script_path}")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error executing SQL script {script_path}: {e}")

    def _create_tables(self):
        """Create tables if they do not exist."""
        self._execute_sql_script(str(self.base_dir / "scripts/create_tables.sql"))

    def _seed_data(self):
        """Seed initial data into the common_words table if it is empty."""
        self._execute_sql_script(str(self.base_dir / "scripts/seed_data.sql"))

    def get_user(self, user_id: int) -> Optional[Tuple]:
        """Retrieve a user by their ID."""
        self.cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        return self.cur.fetchone()

    def create_user(self, user_id: int, username: str, first_name: str):
        """Create a new user."""
        try:
            self.cur.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (%s, %s, %s)",
                (user_id, username, first_name),
            )
            self.conn.commit()
        except psycopg2.IntegrityError:
            self.conn.rollback()

    def get_random_word(self, user_id: int) -> Optional[Tuple[str, str]]:
        """Retrieve a random word for the user."""
        try:
            self.cur.execute(
                """
                SELECT english_word, russian_translation FROM (
                    SELECT english_word, russian_translation FROM common_words
                    UNION ALL
                    SELECT english_word, russian_translation FROM user_words 
                    WHERE user_id = %s
                ) AS all_words
                ORDER BY RANDOM()
                LIMIT 1;
                """,
                (user_id,),
            )
            return self.cur.fetchone()
        except Exception as e:
            logger.error(f"Error in get_random_word: {e}")
            return None

    def get_wrong_translations(self, correct_word: str, limit: int = 3) -> List[str]:
        """Retrieve wrong translations for a given word."""
        self.cur.execute(
            """
            SELECT LOWER(russian_translation) 
            FROM common_words 
            WHERE LOWER(russian_translation) != LOWER(%s)
            GROUP BY LOWER(russian_translation)
            ORDER BY RANDOM()
            LIMIT %s;
            """,
            (correct_word.lower(), limit),
        )
        return [row[0] for row in self.cur.fetchall()]

    def add_user_word(self, user_id: int, english_word: str, russian_word: str) -> bool:
        """Add a word to the user's personal dictionary."""
        english_word = english_word.lower()
        russian_word = russian_word.lower()
        try:
            self.cur.execute(
                """
                INSERT INTO user_words (user_id, english_word, russian_translation)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, english_word) DO NOTHING
                """,
                (user_id, english_word, russian_word),
            )
            self.conn.commit()
            return self.cur.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error adding word: {e}")
            return False

    def delete_user_word(self, user_id: int, word: str) -> bool:
        """Delete a word from the user's personal dictionary."""
        query = """
            DELETE FROM user_words
            WHERE user_id = %s AND (
                LOWER(english_word) = LOWER(%s) OR LOWER(russian_translation) = LOWER(%s)
            )
        """
        self.cur.execute(query, (user_id, word, word))
        deleted_rows = self.cur.rowcount
        self.conn.commit()
        return deleted_rows > 0

    def count_user_words(self, user_id: int) -> int:
        """Count the number of words in the user's personal dictionary."""
        self.cur.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (user_id,))
        return self.cur.fetchone()[0]

    def check_word_progress(self, user_id: int, word_id: int, word_type: str) -> bool:
        """Check if a word has been marked as seen by the user."""
        try:
            self.cur.execute(
                "SELECT 1 FROM user_progress WHERE user_id = %s AND word_id = %s AND word_type = %s",
                (user_id, word_id, word_type),
            )
            return bool(self.cur.fetchone())
        except Exception as e:
            logger.error(f"Error in check_word_progress: {e}")
            return False

    def mark_word_as_seen(self, user_id: int, word_id: int, word_type: str, session_start: datetime):
        """Mark a word as seen by the user."""
        try:
            self.cur.execute(
                "INSERT INTO user_progress (user_id, word_id, word_type, added_at) "
                "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
                (user_id, word_id, word_type, session_start),
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error in mark_word_as_seen: {e}")

    def get_user_words(self, user_id: int) -> List[Tuple[str, str]]:
        """Retrieve all words added by the user."""
        try:
            self.cur.execute(
                "SELECT english_word, russian_translation FROM user_words WHERE user_id = %s",
                (user_id,),
            )
            return [(row[0], row[1]) for row in self.cur.fetchall()]
        except Exception as e:
            logger.error(f"Error in get_user_words: {e}")
            return []

    def get_unseen_word(self, user_id: int) -> Optional[Tuple[str, str, str, int]]:
        """Retrieve an unseen word for the user."""
        try:
            query = """
                SELECT english_word, russian_translation, word_type, word_id 
                FROM (
                    SELECT 
                        c.english_word, 
                        c.russian_translation, 
                        'common' AS word_type, 
                        c.id AS word_id,
                        RANDOM() AS sort_key
                    FROM common_words c
                    LEFT JOIN user_progress p 
                        ON c.id = p.word_id 
                        AND p.word_type = 'common' 
                        AND p.user_id = %s
                    WHERE p.word_id IS NULL

                    UNION ALL

                    SELECT 
                        u.english_word, 
                        u.russian_translation, 
                        'user' AS word_type, 
                        u.id AS word_id,
                        RANDOM() AS sort_key
                    FROM user_words u
                    LEFT JOIN user_progress p 
                        ON u.id = p.word_id 
                        AND p.word_type = 'user' 
                        AND p.user_id = %s
                    WHERE p.word_id IS NULL 
                        AND u.user_id = %s
                ) AS combined_data
                ORDER BY sort_key
                LIMIT 1;
            """
            self.cur.execute(query, (user_id, user_id, user_id))
            return self.cur.fetchone()
        except Exception as e:
            logger.error(f"Error in get_unseen_word: {e}")
            return None

    def check_duplicate(self, user_id: int, word: str) -> bool:
        """Check if a word already exists in the database."""
        self.cur.execute(
            """
            (SELECT 1 FROM common_words 
             WHERE LOWER(english_word) = LOWER(%s) OR LOWER(russian_translation) = LOWER(%s))
            UNION ALL
            (SELECT 1 FROM user_words 
             WHERE user_id = %s AND (LOWER(english_word) = LOWER(%s) OR LOWER(russian_translation) = LOWER(%s)))
            LIMIT 1
            """,
            (word, word, user_id, word, word),
        )
        return bool(self.cur.fetchone())

    def update_session_stats(self, user_id: int, learned_words: int, session_duration: int):
        """Update session statistics for the user."""
        try:
            self.cur.execute(
                """
                INSERT INTO session_stats 
                (user_id, session_date, learned_words, session_duration)
                VALUES (%s, NOW(), %s, %s)
                """,
                (user_id, learned_words, session_duration),
            )
            self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving session stats: {e}")

    def count_new_learned_words(self, user_id: int, session_start: datetime, session_end: datetime) -> int:
        """Count the number of new words learned during a session."""
        try:
            if session_start > session_end:
                session_start, session_end = session_end, session_start

            self.cur.execute(
                "SELECT COUNT(*) FROM user_progress "
                "WHERE user_id = %s AND added_at BETWEEN %s AND %s",
                (user_id, session_start, session_end),
            )
            return self.cur.fetchone()[0] or 0
        except Exception as e:
            logger.error(f"Error in count_new_learned_words: {e}")
            return 0

    def close(self):
        """Close the database connection."""
        self.cur.close()
        self.conn.close()
