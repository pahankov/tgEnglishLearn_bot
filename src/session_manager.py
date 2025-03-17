from datetime import datetime, timedelta

from telegram import Update
from telegram.ext import CallbackContext
from src.database import Database
import logging
from src.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)
db = Database()

def save_session_data(user_id, context):
    session_start = context.user_data.get('session_start')
    if not session_start:
        logger.error("Время начала сессии не найдено!")
        return

    session_end = datetime.now()
    duration = round((session_end - session_start).total_seconds() / 60, 1)
    session_end_with_buffer = session_end + timedelta(seconds=1)

    learned_words = db.count_new_learned_words(user_id, session_start, session_end_with_buffer)
    db.update_session_stats(
        user_id=user_id,
        learned_words=learned_words,
        session_duration=duration
    )
    logger.info(f"[DEBUG] Сессия сохранена: learned_words={learned_words}, duration={duration}")

def check_session_timeout(context: CallbackContext):
    user_id = context.job.context['user_id']
    if 'active_session' in context.user_data:
        save_session_data(user_id, context)
        context.bot.send_message(
            user_id,
            "⏳ Сессия завершена из-за неактивности",
            reply_markup=main_menu_keyboard()  # Восстанавливаем меню
        )
        context.user_data.clear()

def end_session(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if 'active_session' in context.user_data:
        save_session_data(user_id, context)
        context.user_data.clear()

    # Возвращаем основное меню
    update.message.reply_text(
        "Сессия завершена",
        reply_markup=main_menu_keyboard()
    )
