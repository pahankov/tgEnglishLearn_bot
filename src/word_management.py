from telegram import Update
from telegram.ext import CallbackContext, ConversationHandler
from src.database import Database
from src.keyboards import main_menu_keyboard  # Импортируем функцию для главного меню
import logging

db = Database()
logger = logging.getLogger(__name__)

# Константы для ConversationHandler
WAITING_WORD, WAITING_DELETE = range(2)

def pluralize_words(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "слово"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return "слова"
    else:
        return "слов"

def add_word(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Введите слово в формате: Английское-Русское (например: apple-яблоко)"
    )
    return WAITING_WORD

def save_word(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip().split('-')

    if len(text) != 2:
        update.message.reply_text(
            "❌ Неверный формат. Попробуйте еще раз.",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    en_word, ru_word = text[0].strip(), text[1].strip()
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

def delete_word(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Введите английское слово для удаления:",
        reply_markup=main_menu_keyboard()
    )
    return WAITING_DELETE

def confirm_delete(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    en_word = update.message.text.strip()
    success = db.delete_user_word(user_id, en_word)

    if success:
        update.message.reply_text(
            f"🗑️ Слово '{en_word}' удалено.",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text(
            "❌ Такого слова нет в вашем списке.",
            reply_markup=main_menu_keyboard()
        )
    return ConversationHandler.END

def show_user_words(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    words = db.get_user_words(user_id)

    if not words:
        update.message.reply_text(
            "📭 У вас пока нет своих слов.",
            reply_markup=main_menu_keyboard()
        )
    else:
        formatted_words = []
        for en, ru in words:
            formatted_en = en.capitalize()
            formatted_ru = ru.capitalize()
            formatted_words.append(f"• {formatted_en} — {formatted_ru}")

        count = len(words)
        word_form = pluralize_words(count)
        text = f"📖 Ваши слова ({count} {word_form}):\n" + "\n".join(formatted_words)
        update.message.reply_text(text, reply_markup=main_menu_keyboard())
