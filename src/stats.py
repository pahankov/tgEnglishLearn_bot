import logging
import io
import matplotlib

from src.handlers import ask_question_handler
from src.keyboards import stats_keyboard
from src.session_manager import send_message_with_tracking

matplotlib.use('Agg')  # Используем backend, не зависящий от дисплея
import matplotlib.pyplot as plt

from telegram import Update
from telegram.ext import CallbackContext
from src import db

logger = logging.getLogger(__name__)

def get_user_statistics(user_id: int) -> dict:
    stats = {}
    try:
        # Запрос для learned_words
        db.cur.execute("SELECT COUNT(*) FROM user_progress WHERE user_id = %s", (user_id,))
        learned = db.cur.fetchone()[0]
        stats['learned_words'] = learned
        logger.info(f"[DEBUG] Всего изучено слов: {learned}")  # Логирование

        # Запрос для added_words
        db.cur.execute("SELECT COUNT(*) FROM user_words WHERE user_id = %s", (user_id,))
        added = db.cur.fetchone()[0]
        stats['added_words'] = added
        logger.info(f"[DEBUG] Всего добавлено слов: {added}")

        # Запрос для session_stats
        db.cur.execute("SELECT session_date, learned_words FROM session_stats WHERE user_id = %s", (user_id,))
        sessions = db.cur.fetchall()
        stats['session_stats'] = sessions
        logger.info(f"[DEBUG] Данные сессий: {sessions}")

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
    logger.info(f"✅ Сообщение пользователя (ID: {update.message.message_id}) сохранено.")

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
        logger.info(f"✅ Сообщение с графиком (ID: {message.message_id}) сохранено.")
    else:
        send_message_with_tracking(
            update, context,
            text="Динамический график недоступен."
        )

def clear_user_sessions(update: Update, context: CallbackContext):
    """Удаляет все данные сессий пользователя."""
    # Сохраняем ID сообщения пользователя (текст кнопки)
    if 'user_messages' not in context.user_data:
        context.user_data['user_messages'] = []
    context.user_data['user_messages'].append(update.message.message_id)
    logger.info(f"✅ Сообщение пользователя (ID: {update.message.message_id}) сохранено.")

    user_id = update.effective_user.id

    try:
        # Удаляем сессии из таблицы session_stats
        db.cur.execute("DELETE FROM session_stats WHERE user_id = %s", (user_id,))
        db.conn.commit()  # Подтверждаем изменения в базе данных
        logger.info(f"[DEBUG] Все сессии пользователя {user_id} удалены.")

        send_message_with_tracking(
            update, context,
            text="🗑 Все данные ваших сессий успешно очищены!",
            reply_markup=stats_keyboard()  # Клавиатура статистики
        )
    except Exception as e:
        logger.error(f"Ошибка при очистке сессий пользователя {user_id}: {e}")
        send_message_with_tracking(
            update, context,
            text="❌ Произошла ошибка при очистке данных.",
            reply_markup=stats_keyboard()  # Клавиатура статистики
        )

def reset_progress_handler(update: Update, context: CallbackContext):
    """Сброс прогресса пользователя."""
    # Проверяем, есть ли callback_query и message
    if not update.callback_query:
        logger.error("❌ Не удалось определить источник обновления.")
        return

    # Проверяем, есть ли сообщение
    if not update.callback_query.message:
        logger.error("❌ Message внутри callback_query отсутствует.")
        update.callback_query.answer("Ошибка: сообщение не найдено.")
        return

    user_id = update.effective_user.id
    try:
        with db.conn:
            db.cur.execute("DELETE FROM user_progress WHERE user_id = %s", (user_id,))
        update.callback_query.answer("✅ Прогресс сброшен!")

        # Передаём update и context в ask_question_handler
        ask_question_handler(update, context)
    except Exception as e:
        logger.error(f"Ошибка сброса: {e}")
        update.callback_query.answer("❌ Ошибка при сбросе прогресса.")
