from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from src.database import Database
from src.keyboards import main_menu_keyboard, add_more_keyboard
from src.yandex_api import YandexDictionaryApi
import os
import logging
import re

logger = logging.getLogger(__name__)

# Инициализация базы и API
db = Database()
api_key = os.getenv("YANDEX_DICTIONARY_API_KEY")
yandex_api = YandexDictionaryApi(api_key=api_key) if api_key else None

# Состояния ConversationHandler
WAITING_WORD, WAITING_DELETE, WAITING_CHOICE = range(3)


def pluralize_words(count: int) -> str:
    """Склонение слова 'слово'"""
    if count % 10 == 1 and count % 100 != 11:
        return "слово"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return "слова"
    return "слов"


def add_word(update: Update, context: CallbackContext) -> int:
    """Начало процесса добавления слова"""
    update.message.reply_text(
        "📝 Введите слово на русском языке:",
        reply_markup=main_menu_keyboard()
    )
    return WAITING_WORD


def save_word(update: Update, context: CallbackContext) -> int:
    """Обработка введенного слова"""
    user_id = update.effective_user.id
    input_text = update.message.text.strip().lower()

    # Валидация ввода
    if len(input_text.split()) > 1:
        update.message.reply_text(
            "❌ Пожалуйста, введите только ОДНО слово!",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    if not re.match(r'^[а-яё\-]+$', input_text):
        update.message.reply_text(
            "❌ Используйте только русские буквы и дефис!",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    # Проверка существования в базе
    if db.check_duplicate(user_id, input_text):
        update.message.reply_text(
            f"❌ Слово '{input_text}' уже существует!",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    # Получение перевода
    try:
        api_response = yandex_api.lookup(input_text, "ru-en")
        if not api_response or not api_response.get('def'):
            raise ValueError("Пустой ответ API")

        first_translation = api_response['def'][0]['tr'][0]['text'].lower()
    except Exception as e:
        logger.error(f"Ошибка перевода: {str(e)}")
        update.message.reply_text(
            "❌ Не удалось получить перевод!",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    # Проверка дубликата перевода
    if db.check_duplicate(user_id, first_translation):
        update.message.reply_text(
            f"❌ Перевод '{first_translation}' уже существует!",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    # Добавление в базу
    if db.add_user_word(user_id, first_translation, input_text):
        count = db.count_user_words(user_id)
        update.message.reply_text(
            f"✅ Успешно добавлено: {input_text} → {first_translation}\n"
            f"📚 Всего слов: {count}",
            reply_markup=add_more_keyboard()
        )
        return WAITING_CHOICE
    else:
        update.message.reply_text(
            "❌ Ошибка при добавлении!",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END


def handle_choice(update: Update, context: CallbackContext) -> int:
    """Обработка выбора после добавления"""
    choice = update.message.text
    if choice == "Добавить ещё ➕":
        update.message.reply_text(
            "📝 Введите следующее слово:",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD
    elif choice == "В меню ↩️":
        update.message.reply_text(
            "🏠 Возвращаемся в главное меню:",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "❌ Используйте кнопки для выбора!",
            reply_markup=add_more_keyboard()
        )
        return WAITING_CHOICE


def delete_word(update: Update, context: CallbackContext) -> int:
    """Начало процесса удаления"""
    update.message.reply_text(
        "🗑 Введите слово для удаления:",
        reply_markup=main_menu_keyboard()
    )
    return WAITING_DELETE


def confirm_delete(update: Update, context: CallbackContext) -> int:
    """Подтверждение удаления"""
    user_id = update.effective_user.id
    word = update.message.text.strip().lower()

    if db.delete_user_word(user_id, word):
        update.message.reply_text(
            f"✅ Слово '{word}' успешно удалено!",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text(
            f"❌ Слово '{word}' не найдено!",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END


def show_user_words(update: Update, context: CallbackContext):
    """Показ списка слов"""
    user_id = update.effective_user.id
    try:
        words = db.get_user_words(user_id)
        if not words:
            update.message.reply_text(
                "📭 Ваш словарь пока пуст!",
                reply_markup=main_menu_keyboard()
            )
            return

        formatted = [f"• {en.capitalize()} → {ru.capitalize()}" for en, ru in words]
        count = len(words)
        update.message.reply_text(
            f"📖 Ваши слова ({count} {pluralize_words(count)}):\n" + "\n".join(formatted),
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка показа слов: {str(e)}")
        update.message.reply_text(
            "❌ Ошибка при загрузке слов!",
            reply_markup=main_menu_keyboard()
        )
