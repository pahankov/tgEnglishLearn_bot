from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from src import db
from src.keyboards import main_menu_keyboard, add_more_keyboard, delete_more_keyboard
from src.yandex_api import YandexDictionaryApi
import os
import logging
import re

# ================== Настройки логирования ==================
logger = logging.getLogger(__name__)

# ================== Инициализация компонентов ==================
api_key = os.getenv("YANDEX_DICTIONARY_API_KEY")
yandex_api = YandexDictionaryApi(api_key=api_key) if api_key else None

# ================== Состояния ConversationHandler ==================
WAITING_WORD, WAITING_DELETE = range(2)

# ================== Утилиты ==================
def pluralize_words(count: int) -> str:
    """Склонение слова 'слово' по числам"""
    last_digit = count % 10
    if last_digit == 1 and count % 100 != 11:
        return "слово"
    elif 2 <= last_digit <= 4 and not 11 <= count % 100 <= 19:
        return "слова"
    return "слов"

# ================== Добавление слов ==================
def add_word(update: Update, context: CallbackContext) -> int:
    """Начало процесса добавления слова"""
    update.message.reply_text(
        text="📝 Введите слово на русском языке:",
        reply_markup=add_more_keyboard()
    )
    return WAITING_WORD

def save_word(update: Update, context: CallbackContext) -> int:
    """Обработка введенного слова и сохранение в БД"""
    user_id = update.effective_user.id
    input_text = update.message.text.strip().lower()

    # Проверяем, не нажал ли пользователь "Назад ↩️"
    if input_text == "назад ↩️":
        return handle_back_to_menu(update, context)

    # Проверка на пустой ввод
    if not input_text:
        update.message.reply_text("❌ Введите слово!", reply_markup=add_more_keyboard())
        return WAITING_WORD

    # Проверка на одно слово
    if len(input_text.split()) > 1:
        update.message.reply_text("❌ Введите только ОДНО слово!", reply_markup=add_more_keyboard())
        return WAITING_WORD

    # Проверка на русские буквы
    if not re.match(r'^[а-яё\-]+$', input_text):
        update.message.reply_text("❌ Используйте только русские буквы!", reply_markup=add_more_keyboard())
        return WAITING_WORD

    # Проверка на дубликаты
    if db.check_duplicate(user_id, input_text):
        update.message.reply_text(
            f"❌ Слово '{input_text.capitalize()}' уже существует!",
            reply_markup=add_more_keyboard()
        )
        return WAITING_WORD

    # Получение перевода через API
    try:
        api_response = yandex_api.lookup(input_text, "ru-en")
        if not api_response or not api_response.get('def'):
            raise ValueError("Пустой ответ API")

        first_translation = api_response['def'][0]['tr'][0]['text'].lower()
    except Exception as e:
        logger.error(f"Ошибка перевода: {str(e)}")
        update.message.reply_text("❌ Не удалось получить перевод!", reply_markup=add_more_keyboard())
        return WAITING_WORD

    # Проверка на дубликат перевода
    if db.check_duplicate(user_id, first_translation):
        update.message.reply_text(
            f"❌ Перевод '{first_translation.capitalize()}' уже существует!",
            reply_markup=add_more_keyboard()
        )
        return WAITING_WORD

    # Добавление слова в базу данных
    if db.add_user_word(user_id, first_translation, input_text):
        count = db.count_user_words(user_id)
        update.message.reply_text(
            f"✅ Успешно добавлено: {input_text.capitalize()} по слову {first_translation.capitalize()}\n"
            f"📚 Всего слов добавлено: {count}",
            reply_markup=add_more_keyboard()
        )
    else:
        update.message.reply_text("❌ Ошибка при добавлении!", reply_markup=main_menu_keyboard())
        return ConversationHandler.END

    return WAITING_WORD

# ================== Удаление слов ==================
def delete_word(update: Update, context: CallbackContext) -> int:
    """Начало процесса удаления"""
    update.message.reply_text(
        text="🗑 Введите слово для удаления (русское или английское):",
        reply_markup=delete_more_keyboard()
    )
    return WAITING_DELETE

def confirm_delete(update: Update, context: CallbackContext) -> int:
    """Обработка удаления и предложение продолжить"""
    user_id = update.effective_user.id
    word = update.message.text.strip().lower()

    # Проверяем, не нажал ли пользователь "Назад ↩️"
    if word == "назад ↩️":
        return handle_back_to_menu(update, context)

    # Логика удаления слова
    if db.delete_user_word(user_id, word):
        update.message.reply_text(
            f"✅ Слово/перевод '{word}' успешно удалено!",
            reply_markup=delete_more_keyboard()
        )
    else:
        update.message.reply_text(
            f"❌ Слово '{word}' не найдено в вашем словаре!",
            reply_markup=delete_more_keyboard()
        )

    return WAITING_DELETE

# ================== Обработка кнопки "Назад" ==================
def handle_back_to_menu(update: Update, context: CallbackContext):
    """Обработчик кнопки 'Назад' с полным сбросом состояния"""
    context.user_data.clear()  # Очищаем временные данные
    update.message.reply_text(
        "🏠 Возвращаемся в главное меню:",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END

# ================== Показ слов ==================
def show_user_words(update: Update, context: CallbackContext):
    """Отображение списка пользовательских слов"""
    user_id = update.effective_user.id
    try:
        words = db.get_user_words(user_id)
        if not words:
            update.message.reply_text(
                "📭 Ваш словарь пока пуст!",
                reply_markup=main_menu_keyboard()
            )
            return

        formatted = [f"• {en.capitalize()} - {ru.capitalize()}" for en, ru in words]
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