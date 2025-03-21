from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext
from src import db
import logging
from src.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)


def save_session_data(user_id, context):
    session_start = context.user_data.get('session_start')
    if not session_start:
        logger.error("Время начала сессии не найдено!")
        return

    session_end = datetime.now()
    duration = int((session_end - session_start).total_seconds())
    session_end_with_buffer = session_end + timedelta(seconds=1)

    learned_words = db.count_new_learned_words(user_id, session_start, session_end_with_buffer)
    db.update_session_stats(
        user_id=user_id,
        learned_words=learned_words,
        session_duration=duration
    )
    logger.info(f"[DEBUG] Сессия сохранена: learned_words={learned_words}, duration={duration}")
    logger.info(f"[DEBUG] Время сессии: start={session_start}, end={session_end}, duration={duration} сек")
    logger.info(f"[DEBUG] Найдено новых слов: {learned_words}")


def check_session_timeout(context: CallbackContext):
    job = context.job
    if not job:
        logger.error("Задача не найдена")
        return

    # Получаем данные из контекста задачи
    user_id = job.context.get('user_id')
    session_start_ts = job.context.get('session_start')

    if not user_id or not session_start_ts:
        logger.error("Недостаточно данных в контексте задачи")
        return

    # Конвертируем timestamp обратно в datetime
    session_start = datetime.fromtimestamp(session_start_ts)
    session_end = datetime.now()
    duration = int((session_end - session_start).total_seconds())

    # Сохраняем сессию через прямой запрос к БД
    try:
        learned_words = db.count_new_learned_words(
            user_id=user_id,
            session_start=session_start,
            session_end=session_end
        )
        db.update_session_stats(
            user_id=user_id,
            learned_words=learned_words,
            session_duration=duration
        )
        logger.info(f"[DEBUG] Сессия сохранена: user_id={user_id}, words={learned_words}, duration={duration} сек")
    except Exception as e:
        logger.error(f"Ошибка сохранения сессии: {e}")

    # Отправляем уведомление
    context.bot.send_message(
        chat_id=user_id,
        text="⏳ Сессия завершена из-за неактивности",
        reply_markup=main_menu_keyboard()
    )




def end_session(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if 'active_session' in context.user_data:
        save_session_data(user_id, context)
        context.user_data.clear()

    # Сначала удаляем предыдущую клавиатуру
    update.message.reply_text(
        "⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove()
    )

    # Затем отправляем сообщение с основным меню
    update.message.reply_text(
        "Сессия завершена",
        reply_markup=main_menu_keyboard()
    )

