from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from src.database import Database
from src.keyboards import main_menu_keyboard  # Импортируем функцию для главного меню
from dotenv import load_dotenv  # Для загрузки переменных окружения
import os
from src.yandex_api import YandexDictionaryApi  # Импортируем API-клиент
import logging

# Настройка логирования
db = Database()
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()

# Инициализация Yandex API
api_key = os.getenv("YANDEX_DICTIONARY_API_KEY")
if not api_key:
    raise ValueError("Ошибка: токен Яндекс API не найден. Проверьте файл .env.")
yandex_api = YandexDictionaryApi(api_key=api_key)

# Константы для ConversationHandler
WAITING_WORD, WAITING_DELETE = range(2)


def pluralize_words(count: int) -> str:
    """
    Склоняет слово "слово" в зависимости от числа.
    """
    if count % 10 == 1 and count % 100 != 11:
        return "слово"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return "слова"
    else:
        return "слов"


def add_word(update: Update, context: CallbackContext) -> int:
    """
    Начинает процесс добавления нового слова (в формате английское-русское).
    """
    update.message.reply_text(
        "Введите слово например: яблоко",
        reply_markup=main_menu_keyboard()
    )
    return WAITING_WORD


def save_word(update: Update, context: CallbackContext) -> int:
    """
    Сохраняет русское слово, добавленное пользователем, и добавляет его перевод через Яндекс API.
    """
    user_id = update.effective_user.id
    ru_word = update.message.text.strip()

    # Проверяем, что текст является валидным русским словом
    if not ru_word.isalpha():
        update.message.reply_text(
            "❌ Некорректное слово. Введите одно русское слово без пробелов и символов.",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    try:
        # Получаем перевод через Яндекс API
        en_translation = yandex_api.lookup(ru_word, "ru-en")
        if not en_translation:
            update.message.reply_text(
                f"❌ Перевод для слова '{ru_word}' не найден. Попробуйте другое слово.",
                reply_markup=main_menu_keyboard()
            )
            return WAITING_WORD

        # Логируем успешный перевод
        logger.info(f"Перевод для '{ru_word}': '{en_translation}'.")
    except Exception as e:
        logger.error(f"Ошибка при обращении к Яндекс.Словарю для '{ru_word}': {e}")
        update.message.reply_text(
            "❌ Произошла ошибка при запросе. Попробуйте снова.",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    # Добавляем слово в базу данных
    try:
        success = db.add_user_word(user_id, en_translation, ru_word)
        if success:
            count = db.count_user_words(user_id)
            word_form = pluralize_words(count)
            update.message.reply_text(
                f"✅ Слово '{ru_word}' добавлено с переводом '{en_translation}'.\n"
                f"Теперь у вас {count} {word_form} в вашем словаре.",
                reply_markup=main_menu_keyboard()
            )
            logger.info(f"Пользователь {user_id}: слово '{ru_word}' добавлено с переводом '{en_translation}'.")
        else:
            update.message.reply_text(
                f"❌ Слово '{ru_word}' с переводом '{en_translation}' уже есть в вашем списке.",
                reply_markup=main_menu_keyboard()
            )
            logger.warning(f"Пользователь {user_id} пытался добавить существующее слово: '{ru_word}' ({en_translation}).")
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Ошибка при добавлении слова '{ru_word}': {e}")
        update.message.reply_text(
            "❌ Произошла ошибка при добавлении слова. Попробуйте снова.",
            reply_markup=main_menu_keyboard()
        )
    return WAITING_WORD


def delete_word(update: Update, context: CallbackContext) -> int:
    """
    Начинает процесс удаления слова (на русском или английском языке).
    """
    update.message.reply_text(
        "Введите слово, которое вы хотите удалить (на русском или английском):",
        reply_markup=main_menu_keyboard()
    )
    return WAITING_DELETE


def confirm_delete(update: Update, context: CallbackContext) -> int:
    """
    Удаляет слово, введённое пользователем (на русском или английском языке).
    """
    user_id = update.effective_user.id
    word = update.message.text.strip().lower()

    try:
        query = """
            DELETE FROM user_words
            WHERE user_id = %s AND (russian_translation = %s OR english_word = %s)
        """
        db.cur.execute(query, (user_id, word, word))
        if db.cur.rowcount > 0:
            db.conn.commit()
            update.message.reply_text(
                f"🗑️ Слово '{word}' успешно удалено.",
                reply_markup=main_menu_keyboard()
            )
        else:
            update.message.reply_text(
                f"❌ Слово '{word}' не найдено в вашем списке.",
                reply_markup=main_menu_keyboard()
            )
    except Exception as e:
        db.conn.rollback()
        logger.error(f"Ошибка при удалении слова '{word}': {e}")
        update.message.reply_text(
            "❌ Произошла ошибка при удалении слова. Попробуйте снова.",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END


def show_user_words(update: Update, context: CallbackContext):
    """
    Отображает список слов, добавленных пользователем.
    """
    user_id = update.effective_user.id
    try:
        words = db.get_user_words(user_id)
        if not words:
            update.message.reply_text(
                "📭 У вас пока нет своих слов.",
                reply_markup=main_menu_keyboard()
            )
        else:
            formatted_words = [
                f"• {en.capitalize()} — {ru.capitalize()}" for en, ru in words
            ]

            count = len(words)
            word_form = pluralize_words(count)
            text = f"📖 Ваши слова ({count} {word_form}):\n" + "\n".join(formatted_words)
            update.message.reply_text(text, reply_markup=main_menu_keyboard())
    except Exception as e:
        logger.error(f"Ошибка при отображении списка слов: {e}")
        update.message.reply_text(
            "❌ Произошла ошибка при отображении списка слов. Попробуйте снова.",
            reply_markup=main_menu_keyboard()
        )
