from telegram import Update
from telegram.ext import CallbackContext
from src.database import Database
import logging

logger = logging.getLogger(__name__)
db = Database()

def get_user_statistics(user_id: int) -> str:
    """
    Собирает статистику по пользователю:
      - Количество изученных слов (на основе таблицы user_progress)
      - Процент правильных ответов (в данной логике 100%, так как сохраняются только правильно отгаданные слова)
      - Динамика обучения (данные пока не собираются)
    Возвращает отформатированный строковый отчет.
    """
    try:
        # Получаем количество изученных слов из таблицы user_progress
        db.cur.execute("SELECT COUNT(*) FROM user_progress WHERE user_id = %s", (user_id,))
        learned_words = db.cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Ошибка получения статистики для user_id {user_id}: {e}")
        learned_words = 0

    # В текущей реализации, так как в таблице user_progress записываются только правильно отгаданные слова,
    # процент правильных ответов считается равным 100%.
    correct_percent = 100

    stats_text = (
        f"📊 **Ваша статистика**:\n\n"
        f"Вы изучили: **{learned_words}** слов(а).\n"
        f"Процент правильных ответов: **{correct_percent}%**.\n"
        f"Динамика обучения: данные пока не собираются."
    )
    return stats_text

def stats_handler(update: Update, context: CallbackContext):
    """
    Обработчик, вызываемый при запросе статистики.
    Отправляет пользователю сообщение с его статистикой.
    """
    user_id = update.effective_user.id
    stats_text = get_user_statistics(user_id)
    update.message.reply_text(stats_text, parse_mode="Markdown")
