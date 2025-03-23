from datetime import datetime, timedelta
import telegram
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import CallbackContext, ConversationHandler
from src import db
import logging
from src.keyboards import main_menu_keyboard, MENU_BUTTON

logger = logging.getLogger(__name__)

# Константы для таймаута сессии
SESSION_TIMEOUT = 900  # 15 минут в секундах


def save_session_data(user_id, context):
    """Сохраняет статистику сессии в базу данных."""
    session_start = context.user_data.get("session_start")
    if not session_start:
        logger.error("Время начала сессии не найдено! Данные не будут сохранены.")
        return

    session_end = datetime.now()
    duration = int((session_end - session_start).total_seconds())

    try:
        learned_words = db.count_new_learned_words(
            user_id=user_id,
            session_start=session_start,
            session_end=session_end + timedelta(seconds=1),
        )
        db.update_session_stats(
            user_id=user_id,
            learned_words=learned_words,
            session_duration=duration,
        )
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных сессии: {e}")


def check_session_timeout(context: CallbackContext):
    """Автоматическое завершение сессии по таймауту."""
    job = context.job
    if not job or "user_id" not in job.context or "session_start" not in job.context:
        logger.error("Недостаточно данных для завершения по таймауту.")
        return

    user_id = job.context["user_id"]
    session_start = datetime.fromtimestamp(job.context["session_start"])
    session_end = datetime.now()
    duration = int((session_end - session_start).total_seconds())

    try:
        learned_words = db.count_new_learned_words(
            user_id=user_id,
            session_start=session_start,
            session_end=session_end,
        )
        db.update_session_stats(
            user_id=user_id,
            learned_words=learned_words,
            session_duration=duration,
        )
        context.bot.send_message(
            chat_id=user_id,
            text="⏳ Ваша сессия завершена из-за неактивности.",
            reply_markup=main_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка при завершении сессии по таймауту: {e}")


def end_session(update: Update, context: CallbackContext):
    """Завершает текущую сессию вручную."""
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    context.user_data["user_messages"].append(update.message.message_id)

    user_id = update.effective_user.id

    if "active_session" in context.user_data:
        save_session_data(user_id, context)
        context.user_data.clear()

    send_message_with_tracking(
        update, context,
        text="⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove(),
    )
    send_message_with_tracking(
        update, context,
        text="Сессия завершена. Возвращаем вас в главное меню.",
        reply_markup=main_menu_keyboard(),
    )


def start_session(update: Update, context: CallbackContext):
    """Инициализация новой сессии."""
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    context.user_data["user_messages"].append(update.message.message_id)

    delete_bot_messages(update, context)

    user_id = update.effective_user.id
    session_start = datetime.now()
    context.user_data.update({
        "session_start": session_start,
        "correct_answers": 0,
        "active_session": True,
        "job": None,
    })
    job = context.job_queue.run_once(
        callback=check_session_timeout,
        when=SESSION_TIMEOUT,
        context={
            "user_id": user_id,
            "session_start": session_start.timestamp(),
        },
        name=str(user_id),
    )
    context.user_data["job"] = job

    send_message_with_tracking(
        update, context,
        text="Сессия началась!",
        reply_markup=ReplyKeyboardMarkup([[MENU_BUTTON]], resize_keyboard=True),
    )

    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("Произношение слова 🔊", callback_data="pronounce_word")]
    ])
    message = context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Вы можете прослушать произношение слова здесь:",
        reply_markup=button,
    )

    if "bot_messages" not in context.user_data:
        context.user_data["bot_messages"] = []
    context.user_data["bot_messages"].append(message.message_id)


def update_session_timer(context: CallbackContext, user_id: int):
    """Обновление таймера сессии."""
    if "job" in context.user_data:
        try:
            context.user_data["job"].schedule_removal()
        except Exception as e:
            logger.error(f"Ошибка удаления задачи: {e}")

    new_job = context.job_queue.run_once(
        callback=check_session_timeout,
        when=SESSION_TIMEOUT,
        context={
            "user_id": user_id,
            "session_start": context.user_data["session_start"].timestamp(),
        },
        name=str(user_id),
    )
    context.user_data["job"] = new_job


def delete_bot_messages(update: Update, context: CallbackContext):
    """Удаление всех сообщений бота и пользователя, сохранённых в user_data."""
    chat_id = update.effective_chat.id

    if "bot_messages" in context.user_data:
        for message_id in context.user_data["bot_messages"]:
            try:
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except telegram.error.BadRequest as e:
                if "Message to delete not found" not in str(e):
                    logger.warning(f"Ошибка удаления сообщения бота {message_id}: {e}")
            except Exception as e:
                logger.error(f"Неизвестная ошибка при удалении сообщения бота {message_id}: {e}")

        context.user_data["bot_messages"] = []

    if "user_messages" in context.user_data:
        for message_id in context.user_data["user_messages"]:
            try:
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except telegram.error.BadRequest as e:
                if "Message to delete not found" not in str(e):
                    logger.warning(f"Ошибка удаления сообщения пользователя {message_id}: {e}")
            except Exception as e:
                logger.error(f"Неизвестная ошибка при удалении сообщения пользователя {message_id}: {e}")

        context.user_data["user_messages"] = []


def send_message_with_tracking(update: Update, context: CallbackContext, text: str, reply_markup=None, parse_mode=None, is_user_message=False):
    """Отправка сообщения и сохранение его ID."""
    if is_user_message:
        message_id = update.message.message_id
    else:
        if update.message:
            message = update.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        elif update.callback_query and update.callback_query.message:
            message = update.callback_query.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
            )
        else:
            logger.error("Не удалось определить источник обновления.")
            return
        message_id = message.message_id

    if "bot_messages" not in context.user_data:
        context.user_data["bot_messages"] = []
    context.user_data["bot_messages"].append(message_id)


def handle_menu_button(update: Update, context: CallbackContext):
    """Обработка нажатия на кнопку 'В меню ↩️'."""
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    context.user_data["user_messages"].append(update.message.message_id)

    user_id = update.effective_user.id

    if "active_session" in context.user_data:
        save_session_data(user_id, context)
        context.user_data.clear()

    delete_bot_messages(update, context)

    send_message_with_tracking(
        update, context,
        text="🏠 Возвращаемся в главное меню:",
        reply_markup=main_menu_keyboard(),
    )

    return ConversationHandler.END
