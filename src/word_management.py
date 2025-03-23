from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from src import db
from src.keyboards import main_menu_keyboard, add_more_keyboard, delete_more_keyboard
from src.session_manager import delete_bot_messages, send_message_with_tracking
from src.yandex_api import YandexDictionaryApi
import os
import logging
import re

logger = logging.getLogger(__name__)

# Инициализация компонентов
api_key = os.getenv("YANDEX_DICTIONARY_API_KEY")
yandex_api = YandexDictionaryApi(api_key=api_key) if api_key else None

# Состояния ConversationHandler
WAITING_WORD, WAITING_DELETE = range(2)


def pluralize_words(count: int) -> str:
    """Склонение слова 'слово' по числам."""
    last_digit = count % 10
    if last_digit == 1 and count % 100 != 11:
        return "слово"
    elif 2 <= last_digit <= 4 and not 11 <= count % 100 <= 19:
        return "слова"
    return "слов"


def add_word(update: Update, context: CallbackContext) -> int:
    """Начало процесса добавления слова."""
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    context.user_data["user_messages"].append(update.message.message_id)

    delete_bot_messages(update, context)

    send_message_with_tracking(
        update, context,
        text="📝 Введите слово на русском языке:",
        reply_markup=add_more_keyboard(),
    )
    return WAITING_WORD


def save_word(update: Update, context: CallbackContext) -> int:
    """Обработка введенного слова и сохранение в БД."""
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    context.user_data["user_messages"].append(update.message.message_id)

    user_id = update.effective_user.id
    input_text = update.message.text.strip().lower()

    if input_text == "назад ↩️":
        return handle_back_to_menu(update, context)

    if not input_text:
        send_message_with_tracking(
            update, context,
            text="❌ Введите слово!",
            reply_markup=add_more_keyboard(),
        )
        return WAITING_WORD

    if len(input_text.split()) > 1:
        send_message_with_tracking(
            update, context,
            text="❌ Введите только ОДНО слово!",
            reply_markup=add_more_keyboard(),
        )
        return WAITING_WORD

    if not re.match(r"^[а-яё\-]+$", input_text):
        send_message_with_tracking(
            update, context,
            text="❌ Используйте только русские буквы!",
            reply_markup=add_more_keyboard(),
        )
        return WAITING_WORD

    if db.check_duplicate(user_id, input_text):
        send_message_with_tracking(
            update, context,
            text=f"❌ Слово '{input_text.capitalize()}' уже существует!",
            reply_markup=add_more_keyboard(),
        )
        return WAITING_WORD

    try:
        api_response = yandex_api.lookup(input_text, "ru-en")
        if not api_response or not api_response.get("def"):
            raise ValueError("Пустой ответ API")

        first_translation = api_response["def"][0]["tr"][0]["text"].lower()
    except Exception as e:
        logger.error(f"Ошибка перевода: {str(e)}")
        send_message_with_tracking(
            update, context,
            text="❌ Не удалось получить перевод!",
            reply_markup=add_more_keyboard(),
        )
        return WAITING_WORD

    if db.check_duplicate(user_id, first_translation):
        send_message_with_tracking(
            update, context,
            text=f"❌ Перевод '{first_translation.capitalize()}' уже существует!",
            reply_markup=add_more_keyboard(),
        )
        return WAITING_WORD

    if db.add_user_word(user_id, first_translation, input_text):
        count = db.count_user_words(user_id)
        send_message_with_tracking(
            update, context,
            text=f"✅ Успешно добавлено: {input_text.capitalize()} по слову {first_translation.capitalize()}\n"
                 f"📚 Всего слов добавлено: {count}",
            reply_markup=add_more_keyboard(),
        )
    else:
        send_message_with_tracking(
            update, context,
            text="❌ Ошибка при добавлении!",
            reply_markup=main_menu_keyboard(),
        )
        return ConversationHandler.END

    return WAITING_WORD


def delete_word(update: Update, context: CallbackContext) -> int:
    """Начало процесса удаления."""
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    context.user_data["user_messages"].append(update.message.message_id)

    delete_bot_messages(update, context)

    send_message_with_tracking(
        update, context,
        text="🗑 Введите слово для удаления (русское или английское):",
        reply_markup=delete_more_keyboard(),
    )
    return WAITING_DELETE


def confirm_delete(update: Update, context: CallbackContext) -> int:
    """Обработка удаления и предложение продолжить."""
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    context.user_data["user_messages"].append(update.message.message_id)

    user_id = update.effective_user.id
    word = update.message.text.strip().lower()

    if word == "назад ↩️":
        return handle_back_to_menu(update, context)

    if db.delete_user_word(user_id, word):
        send_message_with_tracking(
            update, context,
            text=f"✅ Слово/перевод '{word}' успешно удалено!",
            reply_markup=delete_more_keyboard(),
        )
    else:
        send_message_with_tracking(
            update, context,
            text=f"❌ Слово '{word}' не найдено в вашем словаре!",
            reply_markup=delete_more_keyboard(),
        )

    return WAITING_DELETE


def handle_back_to_menu(update: Update, context: CallbackContext):
    """Обработчик кнопки 'Назад' с полным сбросом состояния."""
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    context.user_data["user_messages"].append(update.message.message_id)

    delete_bot_messages(update, context)
    context.user_data.clear()

    send_message_with_tracking(
        update, context,
        text="🏠 Возвращаемся в главное меню:",
        reply_markup=main_menu_keyboard(),
    )
    return ConversationHandler.END


def show_user_words(update: Update, context: CallbackContext):
    """Отображение списка пользовательских слов."""
    if "user_messages" not in context.user_data:
        context.user_data["user_messages"] = []
    context.user_data["user_messages"].append(update.message.message_id)

    user_id = update.effective_user.id
    try:
        words = db.get_user_words(user_id)
        if not words:
            send_message_with_tracking(
                update, context,
                text="📭 Ваш словарь пока пуст!",
                reply_markup=main_menu_keyboard(),
            )
            return

        formatted = [f"• {en.capitalize()} - {ru.capitalize()}" for en, ru in words]
        count = len(words)
        send_message_with_tracking(
            update, context,
            text=f"📖 Ваши слова ({count} {pluralize_words(count)}):\n" + "\n".join(formatted),
            reply_markup=main_menu_keyboard(),
        )
    except Exception as e:
        logger.error(f"Ошибка показа слов: {str(e)}")
        send_message_with_tracking(
            update, context,
            text="❌ Ошибка при загрузке слов!",
            reply_markup=main_menu_keyboard(),
        )
