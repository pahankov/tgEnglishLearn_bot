import os
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from src.database import Database
from src.quiz import QuizManager
from src.keyboards import main_menu_keyboard, answer_keyboard
from src.word_management import add_word, save_word, delete_word, confirm_delete, show_user_words, WAITING_WORD, WAITING_DELETE
from src.yandex_api import YandexDictionaryApi
from dotenv import load_dotenv

load_dotenv()

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных и QuizManager
db = Database()
quiz = QuizManager(db)

# Инициализация API Яндекса
YANDEX_API_KEY = os.getenv("YANDEX_DICTIONARY_API_KEY")  # Ключ из переменных окружения
if not YANDEX_API_KEY:
    raise ValueError("Ключ API Яндекс.Словаря (YANDEX_DICTIONARY_API_KEY) не найден в окружении.")
yandex_api = YandexDictionaryApi(api_key=YANDEX_API_KEY)


# Обработчик команды /start
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


# Обработчик вопроса
def ask_question_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    logger.info(f"Пользователь {user_id} запрашивает новый вопрос.")
    question = quiz.get_next_question(user_id)
    if not question:
        logger.info(f"У пользователя {user_id} больше нет новых слов для изучения.")
        keyboard = [[InlineKeyboardButton("Начать заново 🔄", callback_data="reset_progress")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎉 Вы изучили все слова! Отличная работа!",
            reply_markup=reply_markup
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


# Сброс прогресса
def reset_progress_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    logger.info(f"Сброс прогресса для пользователя {user_id}.")
    try:
        db.cur.execute("DELETE FROM user_progress WHERE user_id = %s", (user_id,))
        db.conn.commit()
        row_count = db.cur.rowcount
        logger.info(f"Удалено записей о прогрессе: {row_count}")
        update.callback_query.answer("Прогресс сброшен! Давайте начнем заново.")
        ask_question_handler(update, context)
    except Exception as e:
        logger.error(f"Ошибка при сбросе прогресса для пользователя {user_id}: {e}")
        db.conn.rollback()
        update.callback_query.answer("Ошибка при сбросе прогресса. Попробуйте снова.")


# Обработка нажатий на кнопки
def button_click_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if "current_question" not in context.user_data:
        query.answer("❌ Сессия устарела. Начните новый тест.")
        logger.warning("Сессия устарела: current_question отсутствует.")
        return

    data = query.data.split("_")
    if len(data) < 2:
        query.answer("Некорректный ответ.")
        logger.warning("Некорректный формат данных callback: %s", query.data)
        return

    user_answer = data[1]
    correct_answer = context.user_data["current_question"]["correct_answer"]
    word_id = context.user_data["current_question"]["word_id"]
    word_type = context.user_data["current_question"]["word_type"]

    if user_answer == correct_answer:
        logger.info(f"Пользователь {query.from_user.id} дал правильный ответ.")
        response_text = quiz.get_correct_response()
        query.answer(response_text)
        quiz.mark_word_seen(query.from_user.id, word_id, word_type)
        del context.user_data["current_question"]
        ask_question_handler(update, context)
    else:
        logger.info(f"Пользователь {query.from_user.id} дал неверный ответ.")
        response_text = quiz.get_incorrect_response()
        query.answer(response_text)
        options = context.user_data["current_question"]["options"]
        random.shuffle(options)
        reply_markup = answer_keyboard(options)
        try:
            query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception as e:
            logger.warning("Не удалось обновить клавиатуру: %s", e)


# Проверка и сохранение слова
def save_word_handler(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    russian_word = update.message.text.strip()

    # Проверяем, что введено осмысленное слово
    if not russian_word:
        update.message.reply_text("❌ Пожалуйста, введите осмысленное слово на русском языке.")
        logger.warning(f"Пользователь {user_id} ввёл пустое слово.")
        return WAITING_WORD

    logger.info(f"Пользователь {user_id} добавляет русское слово '{russian_word}'.")

    # Проверяем перевод через API
    api_response = yandex_api.lookup(russian_word, "ru-en")

    if not api_response:
        update.message.reply_text(f"❌ Не удалось найти перевод для '{russian_word}'. Попробуйте другое слово.")
        logger.warning(f"API не вернул перевод для '{russian_word}'.")
        return WAITING_WORD

    try:
        definitions = api_response.get("def", [])
        if not definitions:
            raise ValueError("Пустой ответ API: отсутствуют 'def'.")

        translations = [item["text"] for item in definitions[0].get("tr", [])]
        if not translations:
            raise ValueError("Пустой ответ API: отсутствуют 'tr'.")

        # Приводим перевод к нижнему регистру
        first_translation = translations[0].lower()
        logger.info(f"Первый перевод для '{russian_word}': '{first_translation}'.")
    except (IndexError, KeyError, ValueError) as e:
        logger.error(f"Ошибка при обработке ответа API для '{russian_word}': {e}")
        update.message.reply_text(f"❌ Ошибка при обработке перевода для '{russian_word}'. Попробуйте позже.")
        return WAITING_WORD

    # Приводим русское слово к нижнему регистру
    russian_word = russian_word.lower()

    # Проверяем наличие дубликата в базе данных
    if db.check_duplicate(first_translation, russian_word):
        update.message.reply_text(
            f"❌ Слово '{russian_word}' с переводом '{first_translation}' уже существует в вашем словаре."
        )
        logger.warning(
            f"Дубликат обнаружен: слово '{first_translation}' или перевод '{russian_word}' уже существует для пользователя {user_id}."
        )
        return WAITING_WORD

    # Сохраняем слово в базу данных
    # Было:
    # db.add_user_word(user_id, first_translation, russian_word)

    # Стало:
    success = db.add_user_word(user_id, first_translation, russian_word)
    if not success:
        update.message.reply_text("❌ Это слово уже есть в вашем словаре!")
        return ConversationHandler.END
    logger.info(f"Слово '{first_translation}' успешно добавлено для пользователя {user_id} с переводом '{russian_word}'.")
    update.message.reply_text(f"✅ Слово '{russian_word}' добавлено с переводом '{first_translation}'!")
    return ConversationHandler.END
