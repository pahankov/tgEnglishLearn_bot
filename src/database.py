import psycopg2
import logging
from pathlib import Path
from typing import List, Tuple, Optional
from src.config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        try:
            self.conn = psycopg2.connect(**DB_CONFIG)
            self.cur = self.conn.cursor()
            self.base_dir = Path(__file__).resolve().parent.parent

            logger.info("Создание таблиц...")
            self._create_tables()
            logger.info("Таблицы созданы.")

            logger.info("Заполнение данными...")
            self._seed_data()
            logger.info("Данные загружены.")

            logger.info("Подключение к базе данных успешно установлено.")
        except Exception as e:
            logger.error(f"Ошибка при подключении к базе данных: {e}")
            raise

    def _execute_sql_script(self, script_path: str):
        try:
            with open(script_path, 'r', encoding='utf-8') as f:
                sql = f.read()
            self.cur.execute(sql)
            self.conn.commit()
            logger.info(f"Скрипт {script_path} выполнен успешно.")
        except Exception as e:
            logger.error(f"Ошибка при выполнении скрипта {script_path}: {e}")
            self.conn.rollback()

    def _create_tables(self):
        self._execute_sql_script(str(self.base_dir / "scripts/create_tables.sql"))

    def _seed_data(self):
        self._execute_sql_script(str(self.base_dir / "scripts/seed_data.sql"))

    def get_user(self, user_id: int) -> Optional[Tuple]:
        self.cur.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
        return self.cur.fetchone()

    def create_user(self, user_id: int, username: str, first_name: str):
        try:
            self.cur.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (%s, %s, %s)",
                (user_id, username, first_name)
            )
            self.conn.commit()
        except psycopg2.IntegrityError:
            self.conn.rollback()

    def get_random_word(self, user_id: int) -> Optional[Tuple[str, str]]:
        try:
            self.cur.execute("""
                SELECT english_word, russian_translation FROM (
                    SELECT english_word, russian_translation FROM common_words
                    UNION ALL
                    SELECT english_word, russian_translation FROM user_words 
                    WHERE user_id = %s
                ) AS all_words
                ORDER BY RANDOM()
                LIMIT 1;
            """, (user_id,))
            return self.cur.fetchone()
        except Exception as e:
            logger.error(f"Ошибка в get_random_word: {e}")
            return None

    def get_wrong_translations(self, correct_word: str, limit: int = 3) -> List[str]:
        self.cur.execute("""
            SELECT russian_translation FROM common_words
            WHERE russian_translation != %s
            ORDER BY RANDOM()
            LIMIT %s;
        """, (correct_word, limit))
        return [row[0] for row in self.cur.fetchall()]

    def add_user_word(self, user_id: int, english_word: str, russian_word: str) -> bool:
        """Добавляет слово, возвращает True при успешной вставке"""
        try:
            self.cur.execute("""
                INSERT INTO user_words (user_id, english_word, russian_translation)
                VALUES (%s, LOWER(%s), LOWER(%s))
                ON CONFLICT (user_id, english_word) DO NOTHING
            """, (user_id, english_word, russian_word))
            self.conn.commit()
            return self.cur.rowcount > 0
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Ошибка добавления слова: {e}")
            return False

    def delete_user_word(self, user_id: int, word: str) -> bool:
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
        self.cur.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (user_id,))
        return self.cur.fetchone()[0]

    def close(self):
        self.cur.close()
        self.conn.close()

    def get_user_words(self, user_id: int) -> List[Tuple[str, str]]:
        try:
            self.cur.execute(
                "SELECT english_word, russian_translation FROM user_words WHERE user_id = %s",
                (user_id,)
            )
            return [(row[0], row[1]) for row in self.cur.fetchall()]
        except Exception as e:
            logger.error(f"Ошибка в get_user_words: {e}")
            return []

    def get_unseen_word(self, user_id: int) -> Optional[Tuple[str, str]]:
        try:
            query = """
                SELECT w.english_word, w.russian_translation, 'common' AS word_type, w.word_id
                FROM common_words w
                LEFT JOIN user_progress p ON w.word_id = p.word_id AND p.word_type = 'common' AND p.user_id = %s
                WHERE p.word_id IS NULL
                UNION ALL
                SELECT w.english_word, w.russian_translation, 'user' AS word_type, w.user_word_id
                FROM user_words w
                LEFT JOIN user_progress p ON w.user_word_id = p.word_id AND p.word_type = 'user' AND p.user_id = %s
                WHERE p.word_id IS NULL AND w.user_id = %s
                LIMIT 1;
            """
            self.cur.execute(query, (user_id, user_id, user_id))
            return self.cur.fetchone()
        except Exception as e:
            logger.error(f"Ошибка в get_unseen_word: {e}")
            return None

    def mark_word_as_seen(self, user_id: int, word_id: int, word_type: str):
        try:
            self.cur.execute("""
                INSERT INTO user_progress (user_id, word_id, word_type)
                VALUES (%s, %s, %s)
                ON CONFLICT (user_id, word_id, word_type) DO NOTHING;
            """, (user_id, word_id, word_type))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Ошибка в mark_word_as_seen: {e}")
            self.conn.rollback()

    def check_duplicate(self, user_id: int, word: str) -> bool:
        """Проверяет наличие слова в common_words и user_words"""
        self.cur.execute("""
            (SELECT 1 FROM common_words 
             WHERE LOWER(english_word) = LOWER(%s) OR LOWER(russian_translation) = LOWER(%s))
            UNION ALL
            (SELECT 1 FROM user_words 
             WHERE user_id = %s AND (LOWER(english_word) = LOWER(%s) OR LOWER(russian_translation) = LOWER(%s)))
            LIMIT 1
        """, (word, word, user_id, word, word))
        return bool(self.cur.fetchone())