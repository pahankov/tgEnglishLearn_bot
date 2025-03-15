from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from src.database import Database
from src.keyboards import main_menu_keyboard  # Импортируем функцию для главного меню
import logging

# Настройка логирования
db = Database()
logger = logging.getLogger(__name__)

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
    Начинает процесс добавления нового слова.
    """
    update.message.reply_text("Введите слово в формате: английское-русское (например: apple-яблоко)")
    return WAITING_WORD


def save_word(update: Update, context: CallbackContext) -> int:
    """
    Сохраняет новое слово, добавленное пользователем.
    """
    user_id = update.effective_user.id
    text = update.message.text.strip().split('-')

    if len(text) != 2:
        update.message.reply_text(
            "❌ Неверный формат. Попробуйте еще раз. Введите слово в формате: английское-русское.",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    en_word, ru_word = text[0].strip().lower(), text[1].strip().lower()
    success = db.add_user_word(user_id, en_word, ru_word)

    if success:
        count = db.count_user_words(user_id)
        word_form = pluralize_words(count)
        update.message.reply_text(
            f"✅ Слово добавлено! Теперь у вас {count} {word_form}.",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text(
            "❌ Это слово уже есть в вашем списке.",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END


def delete_word(update: Update, context: CallbackContext) -> int:
    """
    Начинает процесс удаления слова.
    """
    update.message.reply_text(
        "Введите русское слово, которое вы хотите удалить:",
        reply_markup=main_menu_keyboard()
    )
    return WAITING_DELETE


def confirm_delete(update: Update, context: CallbackContext) -> int:
    """
    Удаляет слово, введённое пользователем (английское или русское).
    """
    user_id = update.effective_user.id
    word = update.message.text.strip().lower()

    success = db.delete_user_word(user_id, word)

    if success:
        update.message.reply_text(
            f"🗑️ Слово '{word}' успешно удалено.",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text(
            "❌ Такого слова нет в вашем списке.",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END



def show_user_words(update: Update, context: CallbackContext):
    """
    Отображает список слов, добавленных пользователем.
    """
    user_id = update.effective_user.id
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
