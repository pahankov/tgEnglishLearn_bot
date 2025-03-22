from datetime import datetime, timedelta

from telegram import Update, ReplyKeyboardRemove
from telegram.ext import CallbackContext
from src import db
import logging
from src.keyboards import main_menu_keyboard

logger = logging.getLogger(__name__)

from datetime import datetime, timedelta

from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def save_session_data(user_id, context):
    """Сохраняет статистику сессии в базу данных."""
    logger.info(f"✅ Начало сохранения данных сессии для пользователя {user_id}.")

    session_start = context.user_data.get('session_start')
    if not session_start:
        logger.error("❌ Время начала сессии не найдено! Данные не будут сохранены.")
        return

    session_end = datetime.now()
    duration = int((session_end - session_start).total_seconds())
    logger.info(f"⏱ Время сессии: start={session_start}, end={session_end}, duration={duration} сек.")

    try:
        # Подсчет изученных слов
        learned_words = db.count_new_learned_words(
            user_id=user_id,
            session_start=session_start,
            session_end=session_end + timedelta(seconds=1)
        )
        logger.info(f"📚 Изучено слов за сессию: {learned_words}.")

        # Сохранение данных в базу
        db.update_session_stats(
            user_id=user_id,
            learned_words=learned_words,
            session_duration=duration
        )
        logger.info(
            f"✅ Сессия сохранена в базу данных: user_id={user_id}, слова={learned_words}, длительность={duration} сек.")
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении данных сессии: {e}")


def check_session_timeout(context: CallbackContext):
    """Автоматическое завершение сессии по таймауту."""
    job = context.job
    logger.info("✅ Вызов таймера завершения сессии.")

    if not job or 'user_id' not in job.context or 'session_start' not in job.context:
        logger.error("❌ Недостаточно данных для завершения по таймауту.")
        return

    user_id = job.context['user_id']
    session_start = datetime.fromtimestamp(job.context['session_start'])
    session_end = datetime.now()
    duration = int((session_end - session_start).total_seconds())
    logger.info(
        f"⏱ Таймаут завершения сессии: user_id={user_id}, start={session_start}, end={session_end}, duration={duration} сек.")

    try:
        # Подсчет новых изученных слов
        learned_words = db.count_new_learned_words(
            user_id=user_id,
            session_start=session_start,
            session_end=session_end
        )
        logger.info(f"📚 Изучено слов за сессию по таймауту: {learned_words}.")

        # Сохранение данных о сессии
        db.update_session_stats(
            user_id=user_id,
            learned_words=learned_words,
            session_duration=duration
        )
        logger.info(
            f"✅ Данные сессии сохранены в базу: user_id={user_id}, слова={learned_words}, длительность={duration} сек.")

        # Уведомление пользователя
        context.bot.send_message(
            chat_id=user_id,
            text="⏳ Ваша сессия завершена из-за неактивности.",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"❌ Ошибка при завершении сессии по таймауту: {e}")


def end_session(update: Update, context: CallbackContext):
    """Завершает текущую сессию вручную."""
    user_id = update.effective_user.id
    logger.info(f"✅ Ручное завершение сессии для пользователя {user_id}.")

    if 'active_session' in context.user_data:
        logger.info(f"⏱ Сохранение данных перед очисткой для пользователя {user_id}.")
        save_session_data(user_id, context)
        context.user_data.clear()
        logger.info(f"🗑 Данные сессии очищены для пользователя {user_id}.")

    # Уведомление пользователя
    update.message.reply_text(
        "⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove()
    )
    update.message.reply_text(
        "Сессия завершена. Возвращаем вас в главное меню.",
        reply_markup=main_menu_keyboard()
    )
    logger.info(f"✅ Пользователю {user_id} отправлено уведомление об окончании сессии.")


