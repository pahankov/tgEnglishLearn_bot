from datetime import datetime, timedelta
import telegram
from telegram import Update, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CallbackContext
from src import db
import logging
from src.keyboards import main_menu_keyboard, send_pronounce_button, MENU_BUTTON

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
    # Сохраняем ID сообщения пользователя (текст кнопки)
    if 'user_messages' not in context.user_data:
        context.user_data['user_messages'] = []
    context.user_data['user_messages'].append(update.message.message_id)
    logger.info(f"✅ Сообщение пользователя (ID: {update.message.message_id}) сохранено.")

    user_id = update.effective_user.id
    logger.info(f"✅ Ручное завершение сессии для пользователя {user_id}.")

    if 'active_session' in context.user_data:
        logger.info(f"⏱ Сохранение данных перед очисткой для пользователя {user_id}.")
        save_session_data(user_id, context)
        context.user_data.clear()
        logger.info(f"🗑 Данные сессии очищены для пользователя {user_id}.")

    # Уведомление пользователя
    send_message_with_tracking(
        update, context,
        text="⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove()
    )
    send_message_with_tracking(
        update, context,
        text="Сессия завершена. Возвращаем вас в главное меню.",
        reply_markup=main_menu_keyboard()
    )
    logger.info(f"✅ Пользователю {user_id} отправлено уведомление об окончании сессии.")

# Константы для таймаута сессии
SESSION_TIMEOUT = 900  # 15 минут в секундах

def start_session(update: Update, context: CallbackContext):
    """Инициализация новой сессии."""
    # Сохраняем ID сообщения пользователя (текст кнопки)
    if 'user_messages' not in context.user_data:
        context.user_data['user_messages'] = []
    context.user_data['user_messages'].append(update.message.message_id)
    logger.info(f"✅ Сообщение пользователя (ID: {update.message.message_id}) сохранено.")

    # Удаляем предыдущие сообщения (ботов и пользователя)
    delete_bot_messages(update, context)

    user_id = update.effective_user.id
    session_start = datetime.now()
    context.user_data.update({
        'session_start': session_start,
        'correct_answers': 0,
        'active_session': True,
        'job': None
    })
    job = context.job_queue.run_once(
        callback=check_session_timeout,
        when=SESSION_TIMEOUT,
        context={
            'user_id': user_id,
            'session_start': session_start.timestamp()
        },
        name=str(user_id)
    )
    context.user_data['job'] = job
    send_message_with_tracking(
        update, context,
        text="Сессия началась!",
        reply_markup=ReplyKeyboardMarkup([[MENU_BUTTON]], resize_keyboard=True)
    )
    send_pronounce_button(update.effective_chat.id, context)

def update_session_timer(context: CallbackContext, user_id: int):
    """Обновление таймера сессии."""
    if 'job' in context.user_data:
        try:
            context.user_data['job'].schedule_removal()
        except Exception as e:
            logger.error(f"Ошибка удаления задачи: {e}")

    new_job = context.job_queue.run_once(
        callback=check_session_timeout,
        when=SESSION_TIMEOUT,
        context={
            'user_id': user_id,
            'session_start': context.user_data['session_start'].timestamp()
        },
        name=str(user_id)
    )
    context.user_data['job'] = new_job

def delete_bot_messages(update: Update, context: CallbackContext):
    """Удаление всех сообщений бота и пользователя, сохранённых в user_data."""
    chat_id = update.effective_chat.id

    # Удаляем сообщения бота
    if 'bot_messages' in context.user_data:
        logger.info(f"Удаляем сообщения бота: {context.user_data['bot_messages']}")
        for message_id in context.user_data['bot_messages']:
            try:
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"✅ Сообщение бота (ID: {message_id}) удалено.")
            except telegram.error.BadRequest as e:
                logger.warning(f"❌ Ошибка удаления сообщения бота {message_id}: {e}")
            except Exception as e:
                logger.error(f"❌ Неизвестная ошибка при удалении сообщения бота {message_id}: {e}")

        # Очищаем список сообщений бота
        context.user_data['bot_messages'] = []

    # Удаляем сообщения пользователя
    if 'user_messages' in context.user_data:
        logger.info(f"Удаляем сообщения пользователя: {context.user_data['user_messages']}")
        for message_id in context.user_data['user_messages']:
            try:
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                logger.info(f"✅ Сообщение пользователя (ID: {message_id}) удалено.")
            except telegram.error.BadRequest as e:
                logger.warning(f"❌ Ошибка удаления сообщения пользователя {message_id}: {e}")
            except Exception as e:
                logger.error(f"❌ Неизвестная ошибка при удалении сообщения пользователя {message_id}: {e}")

        # Очищаем список сообщений пользователя
        context.user_data['user_messages'] = []


def send_message_with_tracking(update: Update, context: CallbackContext, text: str, reply_markup=None, parse_mode=None, is_user_message=False):
    """
    Отправка сообщения и сохранение его ID.
    Если is_user_message=True, сохраняем ID сообщения пользователя.
    """
    if is_user_message:
        # Сохраняем ID сообщения пользователя
        message_id = update.message.message_id
    else:
        # Определяем, откуда пришло обновление: из сообщения или callback-запроса
        if update.message:
            message = update.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        elif update.callback_query:
            message = update.callback_query.message.reply_text(
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            logger.error("❌ Не удалось определить источник обновления.")
            return
        message_id = message.message_id

    # Сохраняем ID сообщения в user_data
    if 'bot_messages' not in context.user_data:
        context.user_data['bot_messages'] = []  # Создаём список, если его нет
    context.user_data['bot_messages'].append(message_id)

    logger.info(f"✅ Сообщение (ID: {message_id}) сохранено для последующего удаления.")


def handle_menu_button(update: Update, context: CallbackContext):
    """Обработка нажатия на кнопку 'В меню ↩️'."""
    # Сохраняем ID сообщения пользователя
    if 'user_messages' not in context.user_data:
        context.user_data['user_messages'] = []
    context.user_data['user_messages'].append(update.message.message_id)
    logger.info(f"✅ Сообщение пользователя (ID: {update.message.message_id}) сохранено.")

    # Дальнейшая логика обработки кнопки
    update.message.reply_text("Возвращаемся в меню...", reply_markup=main_menu_keyboard())
