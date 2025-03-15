from typing import List  # Добавляем необходимый импорт
from src.database import Database

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
        return self.db.get_unseen_word(user_id)

    def get_wrong_answers(self, correct_word: str, limit: int = 3) -> List[str]:
        """Возвращает уникальные варианты в нижнем регистре"""
        wrong = self.db.get_wrong_translations(correct_word.lower(), limit)
        return [w.capitalize() for w in wrong]  # Приводим к единому формату



    def mark_word_seen(self, user_id: int, word_id: int, word_type: str):
            """Помечает слово как изученное в базе данных."""
            self.db.mark_word_as_seen(user_id, word_id, word_type)

    def get_correct_response(self) -> str:
        resp = self.correct_responses[self.correct_index]
        self.correct_index = (self.correct_index + 1) % len(self.correct_responses)
        return resp

    def get_incorrect_response(self) -> str:
        resp = self.incorrect_responses[self.incorrect_index]
        self.incorrect_index = (self.incorrect_index + 1) % len(self.incorrect_responses)
        return resp
