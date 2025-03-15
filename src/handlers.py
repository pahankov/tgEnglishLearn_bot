import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from src.database import Database
from src.quiz import QuizManager
from src.keyboards import main_menu_keyboard, answer_keyboard
from src.word_management import add_word, save_word, delete_word, confirm_delete, show_user_words, WAITING_WORD, \
    WAITING_DELETE
from src.yandex_api import YandexDictionaryApi
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)
db = Database()
quiz = QuizManager(db)

YANDEX_API_KEY = os.getenv("YANDEX_DICTIONARY_API_KEY")
if not YANDEX_API_KEY:
    raise ValueError("Ключ API Яндекс.Словаря не найден.")
yandex_api = YandexDictionaryApi(api_key=YANDEX_API_KEY)


def start_handler(update: Update, context: CallbackContext):
    user = update.effective_user
    if not db.get_user(user.id):
        db.create_user(user.id, user.username, user.first_name)
        logger.info(f"Создан пользователь: {user.first_name} (ID: {user.id})")
    else:
        logger.info(f"Пользователь {user.first_name} (ID: {user.id}) уже существует")
    update.message.reply_text(
        f"Привет, {user.first_name}! Я помогу тебе учить английский.",
        reply_markup=main_menu_keyboard()
    )


def ask_question_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    question = quiz.get_next_question(user_id)

    if not question:
        keyboard = [[InlineKeyboardButton("Начать заново 🔄", callback_data="reset_progress")]]
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎉 Вы изучили все слова! Отличная работа!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    word_en, word_ru, word_type, word_id = question
    wrong_answers = quiz.get_wrong_answers(word_ru)
    options = [word_ru] + wrong_answers
    random.shuffle(options)
    reply_markup = answer_keyboard(options)

    context.user_data["current_question"] = {
        "word_en": word_en,
        "correct_answer": word_ru,
        "word_id": word_id,
        "word_type": word_type,
        "options": options,
        "reply_markup": reply_markup
    }

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Переведи слово: *{word_en}*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )


def reset_progress_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        db.cur.execute("DELETE FROM user_progress WHERE user_id = %s", (user_id,))
        db.conn.commit()
        update.callback_query.answer("Прогресс сброшен! Давайте начнем заново.")
        ask_question_handler(update, context)
    except Exception as e:
        logger.error(f"Ошибка сброса прогресса: {e}")
        db.conn.rollback()
        update.callback_query.answer("Ошибка при сбросе.")


def button_click_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if "current_question" not in context.user_data:
        query.answer("❌ Сессия устарела. Начните новый тест.")
        return

    data = query.data.split("_")
    if len(data) < 2:
        query.answer("Некорректный ответ.")
        return

    user_answer = data[1]
    correct_answer = context.user_data["current_question"]["correct_answer"]
    word_id = context.user_data["current_question"]["word_id"]
    word_type = context.user_data["current_question"]["word_type"]

    if user_answer == correct_answer:
        quiz.mark_word_seen(query.from_user.id, word_id, word_type)
        del context.user_data["current_question"]
        query.answer(quiz.get_correct_response())
        ask_question_handler(update, context)
    else:
        options = context.user_data["current_question"]["options"]
        random.shuffle(options)
        try:
            query.edit_message_reply_markup(reply_markup=answer_keyboard(options))
        except Exception as e:
            logger.warning(f"Ошибка обновления клавиатуры: {e}")
        query.answer(quiz.get_incorrect_response())


def save_word_handler(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    ru_word = update.message.text.strip().lower()

    if not ru_word:
        update.message.reply_text("❌ Введите осмысленное слово.")
        return WAITING_WORD

    try:
        api_response = yandex_api.lookup(ru_word, "ru-en")
        if not api_response or not api_response.get('def'):
            update.message.reply_text("❌ Перевод не найден.")
            return WAITING_WORD

        first_translation = api_response['def'][0]['tr'][0]['text'].lower()
    except Exception as e:
        logger.error(f"Ошибка API: {e}")
        update.message.reply_text("❌ Ошибка перевода.")
        return WAITING_WORD

    if db.add_user_word(user_id, first_translation, ru_word):
        update.message.reply_text(f"✅ Слово '{ru_word}' успешно добавлено!")
    else:
        update.message.reply_text(f"❌ Слово '{ru_word}' уже существует!")

    return ConversationHandler.END
