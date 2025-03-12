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
from src.word_management import (
    add_word, save_word, delete_word, confirm_delete, show_user_words, WAITING_WORD, WAITING_DELETE
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

db = Database()

MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Начать тест 🚀"), KeyboardButton("Добавить слово ➕")],
        [KeyboardButton("Удалить слово ➖"), KeyboardButton("Мои слова 📖")]
    ],
    resize_keyboard=True
)

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
    word_info = db.get_unseen_word(user_id)

    if not word_info:
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎉 Вы молодец! Вы изучили все доступные слова. Продолжайте в том же духе!",
            reply_markup=MAIN_MENU_KEYBOARD
        )
        return

    word_en, word_ru, word_type, word_id = word_info
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
        "word_id": word_id,
        "word_type": word_type,
        "options": options,
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
    word_id = context.user_data["current_question"]["word_id"]
    word_type = context.user_data["current_question"]["word_type"]

    if user_answer == correct_answer:
        try:
            query.edit_message_text("✅ Правильно! Молодец!")
        except BadRequest:
            pass

        db.mark_word_as_seen(query.from_user.id, word_id, word_type)

        del context.user_data["current_question"]
        ask_question(update, context)
    else:
        current_question = context.user_data["current_question"]
        options = current_question["options"]
        random.shuffle(options)

        keyboard = []
        for i in range(0, len(options), 2):
            row = []
            for opt in options[i:i + 2]:
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

    # Добавление обработчиков команд и сообщений
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button_click))
    dispatcher.add_handler(MessageHandler(Filters.regex(r'^Начать тест 🚀$'), ask_question))
    dispatcher.add_handler(MessageHandler(Filters.regex(r'^Мои слова 📖$'), show_user_words))

    # Обработчик для добавления и удаления слов
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

    # Настройка главного меню клавиатуры в контексте бота
    context = dispatcher.bot_data
    context["main_menu_keyboard"] = MAIN_MENU_KEYBOARD

    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
