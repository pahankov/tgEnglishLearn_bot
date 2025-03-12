# main.py
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler
from src.config import TOKEN
from src.keyboards import main_menu_keyboard
from src.word_management import show_user_words, add_word, save_word, delete_word, confirm_delete, WAITING_WORD, WAITING_DELETE
from src.handlers import start_handler, ask_question_handler, button_click_handler, reset_progress_handler

def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Обработчики callback-запросов
    dispatcher.add_handler(CallbackQueryHandler(reset_progress_handler, pattern="^reset_progress$"))
    dispatcher.add_handler(CallbackQueryHandler(button_click_handler))

    # Обработчики команд и текстовых сообщений
    dispatcher.add_handler(CommandHandler("start", start_handler))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Начать тест 🚀$"), ask_question_handler))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Мои слова 📖$"), show_user_words))

    # Обработчик для добавления/удаления слов через ConversationHandler
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(r"^Добавить слово ➕$"), add_word),
            MessageHandler(Filters.regex(r"^Удалить слово ➖$"), delete_word)
        ],
        states={
            WAITING_WORD: [MessageHandler(Filters.text & ~Filters.command, save_word)],
            WAITING_DELETE: [MessageHandler(Filters.text & ~Filters.command, confirm_delete)]
        },
        fallbacks=[CommandHandler("cancel", lambda update, context: update.message.reply_text("Действие отменено.", reply_markup=main_menu_keyboard()))]
    )
    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
