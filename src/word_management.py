from psycopg2 import IntegrityError
from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from src.database import Database
from src.keyboards import main_menu_keyboard
from src.yandex_api import YandexDictionaryApi
from dotenv import load_dotenv
import os
import logging

logger = logging.getLogger(__name__)

load_dotenv()
db = Database()
api_key = os.getenv("YANDEX_DICTIONARY_API_KEY")
if not api_key:
    raise ValueError("Токен Яндекс API не найден. Проверьте .env.")
yandex_api = YandexDictionaryApi(api_key=api_key)

WAITING_WORD, WAITING_DELETE = range(2)


def pluralize_words(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "слово"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return "слова"
    else:
        return "слов"


def add_word(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Введите слово, например: яблоко",
        reply_markup=main_menu_keyboard()
    )
    return WAITING_WORD


def save_word(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    ru_word = update.message.text.strip().lower()

    if not ru_word.isalpha():
        update.message.reply_text("❌ Некорректное слово. Используйте только буквы.")
        return WAITING_WORD

    try:
        api_response = yandex_api.lookup(ru_word, "ru-en")
        if not api_response or 'def' not in api_response or not api_response['def']:
            update.message.reply_text("❌ Перевод не найден.")
            return WAITING_WORD

        first_translation = api_response['def'][0]['tr'][0]['text'].lower()
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        update.message.reply_text("❌ Ошибка обработки перевода.")
        return WAITING_WORD

    if db.add_user_word(user_id, first_translation, ru_word):
        count = db.count_user_words(user_id)
        word_form = pluralize_words(count)
        update.message.reply_text(
            f"✅ Слово '{ru_word}' добавлено с переводом '{first_translation}'!\n"
            f"Теперь у вас {count} {word_form}.",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text(
            f"❌ Слово '{ru_word}' с переводом '{first_translation}' уже существует!",
            reply_markup=main_menu_keyboard()
        )

    return ConversationHandler.END


def delete_word(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(
        "Введите слово для удаления (на русском или английском):",
        reply_markup=main_menu_keyboard()
    )
    return WAITING_DELETE


def confirm_delete(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    word = update.message.text.strip().lower()

    if db.delete_user_word(user_id, word):
        update.message.reply_text(
            f"🗑️ Слово '{word}' удалено!",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text(
            f"❌ Слово '{word}' не найдено.",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END


def show_user_words(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        words = db.get_user_words(user_id)
        if not words:
            update.message.reply_text(
                "📭 Ваш словарь пока пуст.",
                reply_markup=main_menu_keyboard()
            )
            return

        formatted = [f"• {en.capitalize()} — {ru.capitalize()}" for en, ru in words]
        count = len(words)
        word_form = pluralize_words(count)
        text = f"📖 Ваши слова ({count} {word_form}):\n" + "\n".join(formatted)
        update.message.reply_text(text, reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка показа слов: {e}")
        update.message.reply_text(
            "❌ Ошибка при загрузке слов.",
            reply_markup=main_menu_keyboard()
        )
