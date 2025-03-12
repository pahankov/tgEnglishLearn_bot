from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.error import BadRequest
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler, CallbackContext,
    MessageHandler, Filters, ConversationHandler
)
from src.database import Database
from src.config import TOKEN
import logging
import random

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()
WAITING_WORD, WAITING_DELETE = range(2)

MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Начать тест 🚀"), KeyboardButton("Добавить слово ➕")],
        [KeyboardButton("Удалить слово ➖"), KeyboardButton("Мои слова 📖")]
    ],
    resize_keyboard=True
)


def pluralize_words(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "слово"
    elif 2 <= count % 10 <= 4 and (count % 100 < 10 or count % 100 >= 20):
        return "слова"
    else:
        return "слов"


def start(update: Update, context: CallbackContext):
    user = update.effective_user
    if not db.get_user(user.id):
        db.create_user(user.id, user.username, user.first_name)

    update.message.reply_text(
        f"Привет, {user.first_name}! Я помогу тебе учить английский. 🎓",
        reply_markup=MAIN_MENU_KEYBOARD
    )


def ask_question(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    word_pair = db.get_random_word(user_id)

    if not word_pair:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Нет доступных слов. Добавьте новые!",
            reply_markup=MAIN_MENU_KEYBOARD
        )
        return

    word_en, word_ru = word_pair
    wrong_answers = db.get_wrong_translations(word_ru, 3)
    options = [word_ru] + wrong_answers
    random.shuffle(options)

    keyboard = [
        [InlineKeyboardButton(options[i], callback_data=f"answer_{options[i]}"),
         InlineKeyboardButton(options[i + 1], callback_data=f"answer_{options[i + 1]}")]
        for i in range(0, len(options), 2)
    ]

    context.user_data["current_question"] = {
        "word_en": word_en,
        "correct_answer": word_ru,
        "reply_markup": InlineKeyboardMarkup(keyboard)
    }

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Переведи слово: *{word_en}*",
        parse_mode="Markdown",
        reply_markup=context.user_data["current_question"]["reply_markup"]
    )


def button_click(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()

    if "current_question" not in context.user_data:
        query.edit_message_text("❌ Сессия устарела. Начните новый тест.")
        return

    user_answer = query.data.split("_")[1]
    correct_answer = context.user_data["current_question"]["correct_answer"]

    if user_answer == correct_answer:
        try:
            query.edit_message_text("✅ Правильно! Молодец!")
        except BadRequest:
            pass  # Игнорируем ошибку, если сообщение уже изменено
        del context.user_data["current_question"]
        ask_question(update, context)
    else:
        current_question = context.user_data["current_question"]
        options = [
            current_question["correct_answer"]
        ] + db.get_wrong_translations(current_question["correct_answer"], 3)
        random.shuffle(options)

        # Генерируем новую клавиатуру с уникальными callback_data
        keyboard = []
        for i in range(0, len(options), 2):
            row = []
            for opt in options[i:i + 2]:
                # Уникальный callback_data для каждой кнопки
                callback_data = f"answer_{opt}_{random.randint(1, 1000)}"
                row.append(InlineKeyboardButton(opt, callback_data=callback_data))
            keyboard.append(row)

        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            query.edit_message_text(
                f"❌ Неверно. Попробуй еще раз!\nПереведи слово: *{current_question['word_en']}*",
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
        except BadRequest:
            logger.warning("Сообщение не было изменено (дубликат).")


def add_word(update: Update, context: CallbackContext):
    update.message.reply_text("Введите слово в формате: Английское-Русское (например: apple-яблоко)")
    return WAITING_WORD


def save_word(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    text = update.message.text.strip().split('-')

    if len(text) != 2:
        update.message.reply_text("❌ Неверный формат. Попробуйте еще раз.")
        return WAITING_WORD

    en_word, ru_word = text[0].strip(), text[1].strip()
    success = db.add_user_word(user_id, en_word, ru_word)

    if success:
        count = db.count_user_words(user_id)
        word_form = pluralize_words(count)
        update.message.reply_text(
            f"✅ Слово добавлено! Теперь у вас {count} {word_form}.",
            reply_markup=MAIN_MENU_KEYBOARD
        )
    else:
        update.message.reply_text("❌ Это слово уже есть в вашем списке.", reply_markup=MAIN_MENU_KEYBOARD)
    return ConversationHandler.END


def delete_word(update: Update, context: CallbackContext):
    update.message.reply_text("Введите английское слово для удаления:")
    return WAITING_DELETE


def confirm_delete(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    en_word = update.message.text.strip()
    success = db.delete_user_word(user_id, en_word)

    if success:
        update.message.reply_text(f"🗑️ Слово '{en_word}' удалено.", reply_markup=MAIN_MENU_KEYBOARD)
    else:
        update.message.reply_text("❌ Такого слова нет в вашем списке.", reply_markup=MAIN_MENU_KEYBOARD)
    return ConversationHandler.END


def show_user_words(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    words = db.get_user_words(user_id)

    if not words:
        update.message.reply_text("📭 У вас пока нет своих слов.", reply_markup=MAIN_MENU_KEYBOARD)
    else:
        formatted_words = []
        for en, ru in words:
            formatted_en = en.capitalize()  # Выводим с заглавной буквы
            formatted_ru = ru.capitalize()
            formatted_words.append(f"• {formatted_en} — {formatted_ru}")

        count = len(words)
        word_form = pluralize_words(count)
        text = f"📖 Ваши слова ({count} {word_form}):\n" + "\n".join(formatted_words)
        update.message.reply_text(text, reply_markup=MAIN_MENU_KEYBOARD)


def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Действие отменено.", reply_markup=MAIN_MENU_KEYBOARD)
    return ConversationHandler.END


def error_handler(update: Update, context: CallbackContext):
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    if update.effective_message:
        update.effective_message.reply_text("⚠️ Произошла ошибка. Попробуйте снова.")


def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button_click))
    dispatcher.add_handler(MessageHandler(Filters.regex(r'^Начать тест 🚀$'), ask_question))
    dispatcher.add_handler(MessageHandler(Filters.regex(r'^Мои слова 📖$'), show_user_words))

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(r'^Добавить слово ➕$'), add_word),
            MessageHandler(Filters.regex(r'^Удалить слово ➖$'), delete_word)
        ],
        states={
            WAITING_WORD: [MessageHandler(Filters.text & ~Filters.command, save_word)],
            WAITING_DELETE: [MessageHandler(Filters.text & ~Filters.command, confirm_delete)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
