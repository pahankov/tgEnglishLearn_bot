import logging
import io
import matplotlib
from telegram import Update
from telegram.ext import CallbackContext
from src.handlers import ask_question_handler
from src.keyboards import stats_keyboard
from src.session_manager import send_message_with_tracking
from src import db

matplotlib.use('Agg')  # Используем backend, не зависящий от дисплея
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


def get_user_statistics(user_id: int) -> dict:
    stats = {}
    try:
        db.cur.execute("SELECT COUNT(*) FROM user_progress WHERE user_id = %s", (user_id,))
        stats['learned_words'] = db.cur.fetchone()[0]

        db.cur.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (user_id,))
        stats['added_words'] = db.cur.fetchone()[0]

        db.cur.execute("SELECT session_date, learned_words FROM session_stats WHERE user_id = %s", (user_id,))
        stats['session_stats'] = db.cur.fetchall()

    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}")

    return stats


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
    в виде текстового отчёта, предоставляет клавиатуру и отправляет график.
    """
    # Сохраняем ID сообщения пользователя (текст кнопки)
    if 'user_messages' not in context.user_data:
        context.user_data['user_messages'] = []
    context.user_data['user_messages'].append(update.message.message_id)

    user_id = update.effective_user.id
    stats = get_user_statistics(user_id)

    # Формирование текста статистики
    text = (
        f"📊 **Ваша статистика:**\n\n"
        f"Изучено слов: **{stats.get('learned_words', 0)}**\n"
        f"Добавлено слов: **{stats.get('added_words', 0)}**\n"
    )

    session_stats = stats.get('session_stats', [])
    if session_stats:
        text += "\n**Статистика сессий:**\n"
        for session in session_stats:
            date_str = session[0].strftime("%Y-%m-%d %H:%M") if hasattr(session[0], "strftime") else str(session[0])
            text += f"• {date_str}: {session[1]} слов\n"
    else:
        text += "\nСтатистика сессий отсутствует.\n"

    # Отправка текста со статистикой
    send_message_with_tracking(
        update, context,
        text=text,
        parse_mode="Markdown"
    )

    # Отправка клавиатуры для действий со статистикой
    send_message_with_tracking(
        update, context,
        text="Выберите действие:",
        reply_markup=stats_keyboard()
    )

    # Генерация и отправка динамического графика
    chart_buf = generate_stats_chart(session_stats)
    if chart_buf:
        # Отправляем график и сохраняем его ID
        message = update.message.reply_photo(photo=chart_buf)
        if 'bot_messages' not in context.user_data:
            context.user_data['bot_messages'] = []
        context.user_data['bot_messages'].append(message.message_id)
    else:
        send_message_with_tracking(
            update, context,
            text="Динамический график недоступен."
        )


def clear_user_sessions(update: Update, context: CallbackContext):
    """Удаляет все данные сессий пользователя."""
    user_id = update.effective_user.id

    try:
        db.cur.execute("DELETE FROM session_stats WHERE user_id = %s", (user_id,))
        db.conn.commit()
        send_message_with_tracking(update, context, text="🗑 Все данные ваших сессий успешно очищены!", reply_markup=stats_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при очистке сессий пользователя {user_id}: {e}")
        send_message_with_tracking(update, context, text="❌ Произошла ошибка при очистке данных.", reply_markup=stats_keyboard())


def reset_progress_handler(update: Update, context: CallbackContext):
    """Сброс прогресса пользователя."""
    if not update.callback_query or not update.callback_query.message:
        logger.error("❌ Не удалось определить источник обновления.")
        return

    user_id = update.effective_user.id
    try:
        with db.conn:
            db.cur.execute("DELETE FROM user_progress WHERE user_id = %s", (user_id,))
        update.callback_query.answer("✅ Прогресс сброшен!")
        ask_question_handler(update, context)
    except Exception as e:
        logger.error(f"Ошибка сброса: {e}")
        update.callback_query.answer("❌ Ошибка при сбросе прогресса.")