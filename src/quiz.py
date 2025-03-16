from datetime import datetime
from typing import List  # Добавляем необходимый импорт
from src.database import Database
from telegram.ext import CallbackContext
from src.keyboards import main_menu_keyboard
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QuizManager:
    def __init__(self, db: Database):
        self.db = db
        self.correct_responses = [
            "✅ Отлично! Молодец! 🎉",
            "🌟 Верно, ты справился! 👍",
            "🔥 Правильно! Продолжай в том же духе!",
            "😎 Молодец! Ответ правильный!",
            "🎊 Замечательно, верно отвечено!"
        ]
        self.incorrect_responses = [
            "❌ Попробуй ещё раз!",
            "😕 Неверно. Дай еще одну попытку!",
            "🚫 Ошибка. Попытайся снова!",
            "🙁 Не угадал. Попробуй ещё раз!",
            "😢 Неправильно. Давай, у тебя получится!"
        ]
        self.correct_index = 0
        self.incorrect_index = 0

    def get_next_question(self, user_id: int) -> tuple:
        question = self.db.get_unseen_word(user_id)
        if not question:
            logger.error(f"[DEBUG] Нет доступных слов для user_id={user_id}")
        return question

    def get_wrong_answers(self, correct_word: str, limit: int = 3) -> List[str]:
        """Возвращает уникальные варианты в нижнем регистре"""
        wrong = self.db.get_wrong_translations(correct_word.lower(), limit)
        return [w.capitalize() for w in wrong]  # Приводим к единому формату

    def mark_word_seen(self, user_id: int, word_id: int, word_type: str, session_start: datetime):
        """Помечает слово как изученное в базе данных."""
        self.db.mark_word_as_seen(user_id, word_id, word_type, session_start)

    def get_correct_response(self) -> str:
        resp = self.correct_responses[self.correct_index]
        self.correct_index = (self.correct_index + 1) % len(self.correct_responses)
        return resp

    def get_incorrect_response(self) -> str:
        resp = self.incorrect_responses[self.incorrect_index]
        self.incorrect_index = (self.incorrect_index + 1) % len(self.incorrect_responses)
        return resp

# quiz.py
def check_session_timeout(context: CallbackContext):
    from src.handlers import _save_session_data
    job = context.job
    user_id = job.user_id
    if 'active_session' in context.user_data:
        _save_session_data(user_id, context)
        context.bot.send_message(
            chat_id=user_id,
            text="Сессия завершена из-за неактивности",
            reply_markup=main_menu_keyboard()
        )
        context.user_data.clear()