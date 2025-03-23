import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from dotenv import load_dotenv

from src import db
from src.quiz import QuizManager
from src.keyboards import main_menu_keyboard, answer_keyboard
from src.sberspeech_api import SberSpeechAPI
from src.yandex_api import YandexDictionaryApi
from src.session_manager import (
    update_session_timer,
    start_session,
    delete_bot_messages,
    send_message_with_tracking,
    save_session_data,
)

# Загрузка переменных окружения
load_dotenv()
logger = logging.getLogger(__name__)
quiz = QuizManager(db)

# Инициализация API Яндекс.Словаря
YANDEX_API_KEY = os.getenv("YANDEX_DICTIONARY_API_KEY")
if not YANDEX_API_KEY:
    raise ValueError("Yandex Dictionary API key not found.")
yandex_api = YandexDictionaryApi(api_key=YANDEX_API_KEY)


def start_handler(update: Update, context: CallbackContext):
    """Обработчик команды /start."""
    user = update.effective_user

    # Удаляем предыдущие сообщения
    delete_bot_messages(update, context)

    # Проверяем, существует ли пользователь, и создаём, если нет
    if not db.get_user(user.id):
        db.create_user(user.id, user.username, user.first_name)
        logger.info(f"User created: {user.first_name} (ID: {user.id})")

    # Отправляем приветственное сообщение
    send_message_with_tracking(
        update,
        context,
        text=f"Привет, {user.first_name}! Я помогу тебе учить английский.",
        reply_markup=main_menu_keyboard(),
    )


def ask_question_handler(update: Update, context: CallbackContext):
    """Генерация нового вопроса и управление сессией."""
    message = update.message or (update.callback_query and update.callback_query.message)
    if not message:
        logger.error("Could not determine the source of the update.")
        return

    user_id = update.effective_user.id

    # Если сессия ещё не начата
    if "active_session" not in context.user_data or not context.user_data["active_session"]:
        start_session(update, context)

    # Обновление таймера сессии
    update_session_timer(context, user_id)

    # Получение следующего вопроса
    question = quiz.get_next_question(user_id)
    if not question:
        if context.user_data.get("active_session"):
            save_session_data(user_id, context)
            context.user_data.clear()
            keyboard = [[InlineKeyboardButton("Начать заново 🔄", callback_data="reset_progress")]]
            send_message_with_tracking(
                update,
                context,
                text="🎉 Вы изучили все слова! Отличная работа!",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        return

    try:
        word_en, word_ru, word_type, word_id = question
    except Exception as e:
        logger.error(f"Error unpacking question data: {e}")
        return

    wrong_answers = list(
        {ans.lower() for ans in quiz.get_wrong_answers(word_ru) if ans.lower() != word_ru.lower()}
    )[:3]
    options = [word_ru.capitalize()] + [ans.capitalize() for ans in wrong_answers]
    random.shuffle(options)

    context.user_data["current_question"] = {
        "word_en": word_en,
        "correct_answer": word_ru.capitalize(),
        "word_id": word_id,
        "word_type": word_type,
        "options": options,
    }

    send_message_with_tracking(
        update,
        context,
        text=f"Переведи слово: *{word_en.capitalize()}*",
        parse_mode="Markdown",
        reply_markup=answer_keyboard(options),
    )


def button_click_handler(update: Update, context: CallbackContext):
    """Обработка ответа пользователя."""
    query = update.callback_query
    if "current_question" not in context.user_data:
        query.answer("❌ Сессия устарела. Начните новый тест.")
        return

    data = query.data.split("_")
    if len(data) < 2:
        query.answer("Некорректный ответ.")
        return

    user_answer = data[1]
    current_question = context.user_data["current_question"]
    correct_answer = current_question["correct_answer"]
    word_id = current_question["word_id"]
    word_type = current_question["word_type"]
    user_id = update.effective_user.id

    if user_answer.lower() == correct_answer.lower():
        if not db.check_word_progress(user_id, word_id, word_type):
            session_start = context.user_data.get("session_start")
            quiz.mark_word_seen(user_id, word_id, word_type, session_start)
        del context.user_data["current_question"]
        query.answer(quiz.get_correct_response())

        try:
            context.bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
        except Exception as e:
            logger.error(f"Error deleting message: {e}")

        ask_question_handler(update, context)
    else:
        options = current_question["options"]
        random.shuffle(options)
        try:
            query.edit_message_reply_markup(reply_markup=answer_keyboard(options))
        except Exception as e:
            logger.warning(f"Error updating keyboard: {e}")
        query.answer(quiz.get_incorrect_response())


def pronounce_word_handler(update: Update, context: CallbackContext):
    """Обработчик для воспроизведения произношения текущего слова."""
    query = update.callback_query
    query.answer()

    current_question = context.user_data.get("current_question")
    if not current_question or "word_en" not in current_question:
        query.answer("❌ Слово не найдено для произношения.", show_alert=True)
        return

    word = current_question["word_en"]
    try:
        sber_speech = SberSpeechAPI()
        audio_file = sber_speech.synthesize_text(word)

        if audio_file:
            with open(audio_file, "rb") as audio:
                message = context.bot.send_audio(chat_id=query.message.chat.id, audio=audio)
                if "bot_messages" not in context.user_data:
                    context.user_data["bot_messages"] = []
                context.user_data["bot_messages"].append(message.message_id)
            logger.info(f"Word '{word}' pronounced successfully.")
        else:
            logger.error("Audio synthesis failed.")
            query.answer("❌ Произошла ошибка при озвучивании слова.", show_alert=True)

    except FileNotFoundError as e:
        logger.error(f"Audio file not found: {e}")
        query.answer("❌ Не удалось найти файл произношения.", show_alert=True)
    except Exception as e:
        logger.error(f"Error in pronounce_word_handler: {e}")
        query.answer("❌ Возникла ошибка при обработке запроса.", show_alert=True)


def handle_menu_button(update: Update, context: CallbackContext):
    """Обработка нажатия на кнопку 'В меню ↩️'."""
    # Сохраняем ID сообщения пользователя (текст кнопки)
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    if update.message:
        context.user_data["user_messages"].append(update.message.message_id)
        logger.info(
            "✅ Сообщение пользователя (ID: %s) сохранено.",
            update.message.message_id,
        )
    else:
        logger.warning("⚠️ Сообщение пользователя отсутствует, сохранение невозможно.")

    user_id = update.effective_user.id

    # Проверка активной сессии
    if "active_session" in context.user_data:
        save_session_data(user_id, context)
        logger.info("✅ Данные сессии сохранены для пользователя %s.", user_id)
    else:
        logger.info("❌ Активная сессия не найдена для пользователя %s.", user_id)

    # Удаляем все сообщения
    delete_bot_messages(update, context)

    # Очищаем временные данные
    context.user_data.clear()
    logger.info("🗑 Данные пользователя очищены для %s.", user_id)

    # Отправляем главное меню
    send_message_with_tracking(
        update,
        context,
        text="🏠 Возвращаемся в главное меню:",
        reply_markup=main_menu_keyboard(),
    )
    logger.info("✅ Пользователю %s отправлено главное меню.", user_id)

    # Завершаем обработку
    return ConversationHandler.END

