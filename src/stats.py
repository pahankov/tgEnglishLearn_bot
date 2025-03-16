import logging
import io
import matplotlib

matplotlib.use('Agg')  # Используем backend, не зависящий от дисплея
import matplotlib.pyplot as plt

from telegram import Update
from telegram.ext import CallbackContext
from src.database import Database

logger = logging.getLogger(__name__)
db = Database()


def get_user_statistics(user_id: int) -> dict:
    """
    Собирает расширенную статистику по пользователю:
      - learned_words: количество изученных слов (из таблицы user_progress);
      - added_words: количество слов, добавленных пользователем (из таблицы user_words);
      - session_stats: статистика сессий (из таблицы session_stats), возвращается как список кортежей (session_date, learned_words).

    Если таблицы или столбцы не существуют, возвращает пустой список сессий.
    """
    stats = {}
    try:
        db.cur.execute("SELECT COUNT(*) FROM user_progress WHERE user_id = %s", (user_id,))
        stats['learned_words'] = db.cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Ошибка получения изученных слов для user_id {user_id}: {e}")
        stats['learned_words'] = 0

    try:
        db.cur.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (user_id,))
        stats['added_words'] = db.cur.fetchone()[0]
    except Exception as e:
        logger.error(f"Ошибка получения добавленных слов для user_id {user_id}: {e}")
        stats['added_words'] = 0

    try:
        # Этот запрос рассчитан на существование таблицы session_stats с нужными столбцами.
        db.cur.execute(
            "SELECT session_date, learned_words FROM session_stats WHERE user_id = %s ORDER BY session_date",
            (user_id,)
        )
        stats['session_stats'] = db.cur.fetchall()  # Ожидается список кортежей (session_date, learned_words)
    except Exception as e:
        logger.error(f"Ошибка получения статистики сессий для user_id {user_id}: {e}")
        stats['session_stats'] = []

    return stats


# stats.py
def generate_stats_chart(session_stats):
    dates = [s[0].strftime("%Y-%m-%d %H:%M") for s in session_stats]
    words = [s[1] for s in session_stats]

    plt.figure(figsize=(10, 5))
    plt.plot(dates, words, marker='o', linestyle='-', color='blue')
    plt.title("Прогресс по сессиям")
    plt.xlabel("Дата")
    plt.ylabel("Изучено слов")
    plt.xticks(rotation=45)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    return buf


def stats_handler(update: Update, context: CallbackContext):
    """
    Обработчик статистики: собирает статистику пользователя, форматирует её
    в виде текстового отчёта и отправляет динамический график (если доступен).
    """
    user_id = update.effective_user.id
    stats = get_user_statistics(user_id)

    text = (
        f"📊 **Ваша статистика:**\n\n"
        f"Изучено слов: **{stats.get('learned_words', 0)}**\n"
        f"Добавлено слов: **{stats.get('added_words', 0)}**\n"
    )

    session_stats = stats.get('session_stats', [])
    if session_stats:
        text += "\n**Статистика сессий:**\n"
        for session in session_stats:
            # Если session_date — объект datetime, можно форматировать через strftime.
            # Если это строка, оставить как есть.
            date_str = session[0].strftime("%Y-%m-%d %H:%M") if hasattr(session[0], "strftime") else str(session[0])
            text += f"• {date_str}: {session[1]} слов\n"
    else:
        text += "\nСтатистика сессий отсутствует.\n"

    update.message.reply_text(text, parse_mode="Markdown")

    chart_buf = generate_stats_chart(session_stats)
    if chart_buf:
        update.message.reply_photo(photo=chart_buf)
    else:
        update.message.reply_text("Динамический график недоступен.")
