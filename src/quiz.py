from datetime import datetime
from typing import List, Optional, Tuple
import logging

from src.database import Database

# Настройка логгера
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class QuizManager:
    def __init__(self, db: Database):
        """Инициализация менеджера викторины."""
        self.db = db
        self.correct_responses = [
            "✅ Отлично! Молодец! 🎉",
            "🌟 Верно, ты справился! 👍",
            "🔥 Правильно! Продолжай в том же духе!",
            "😎 Молодец! Ответ правильный!",
            "🎊 Замечательно, верно отвечено!",
        ]
        self.incorrect_responses = [
            "❌ Попробуй ещё раз!",
            "😕 Неверно. Дай еще одну попытку!",
            "🚫 Ошибка. Попытайся снова!",
            "🙁 Не угадал. Попробуй ещё раз!",
            "😢 Неправильно. Давай, у тебя получится!",
        ]
        self.correct_index = 0
        self.incorrect_index = 0

    def get_next_question(self, user_id: int) -> Optional[Tuple[str, str, str, int]]:
        """Получение следующего вопроса для пользователя."""
        question = self.db.get_unseen_word(user_id)
        if not question:
            logger.info(f"No available words for user_id={user_id}")
        return question

    def get_wrong_answers(self, correct_word: str, limit: int = 3) -> List[str]:
        """Возвращает уникальные варианты неправильных ответов."""
        wrong = self.db.get_wrong_translations(correct_word.lower(), limit)
        return [w.capitalize() for w in wrong]

    def mark_word_seen(self, user_id: int, word_id: int, word_type: str, session_start: datetime):
        """Помечает слово как изученное в базе данных."""
        self.db.mark_word_as_seen(user_id, word_id, word_type, session_start)

    def get_correct_response(self) -> str:
        """Возвращает случайный ответ для правильного ответа."""
        resp = self.correct_responses[self.correct_index]
        self.correct_index = (self.correct_index + 1) % len(self.correct_responses)
        return resp

    def get_incorrect_response(self) -> str:
        """Возвращает случайный ответ для неправильного ответа."""
        resp = self.incorrect_responses[self.incorrect_index]
        self.incorrect_index = (self.incorrect_index + 1) % len(self.incorrect_responses)
        return resp
