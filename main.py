#!/usr/bin/env python3
import logging
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, ConversationHandler
from src.config import TOKEN
from src.keyboards import main_menu_keyboard
from src.word_management import (
    add_word, save_word, delete_word, confirm_delete, show_user_words,
    WAITING_WORD, WAITING_DELETE
)
from src.handlers import start_handler, ask_question_handler, button_click_handler, reset_progress_handler
from src.stats import stats_handler  # Импорт статистического обработчика

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Обрабатываем callback-запросы
    dispatcher.add_handler(CallbackQueryHandler(reset_progress_handler, pattern="^reset_progress$"))
    dispatcher.add_handler(CallbackQueryHandler(button_click_handler))

    # Обрабатываем команду /start
    dispatcher.add_handler(CommandHandler("start", start_handler))

    # Обрабатываем сообщения: кнопки главного меню
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Начать тест 🚀$"), ask_question_handler))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Мои слова 📖$"), show_user_words))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Ваша статистика 📊$"), stats_handler))

    # ConversationHandler для функций добавления/удаления слов
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(r"^Добавить слово ➕$"), add_word),
            MessageHandler(Filters.regex(r"^Удалить слово ➖$"), delete_word)
        ],
        states={
            WAITING_WORD: [MessageHandler(Filters.text & ~Filters.command, save_word)],
            WAITING_DELETE: [MessageHandler(Filters.text & ~Filters.command, confirm_delete)]
        },
        fallbacks=[
            CommandHandler("cancel", lambda update, context: update.message.reply_text(
                "Действие отменено.", reply_markup=main_menu_keyboard()
            ))
        ]
    )
    dispatcher.add_handler(conv_handler)

    dispatcher.add_error_handler(lambda update, context: logger.error("Ошибка:", exc_info=context.error))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
