import logging
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackQueryHandler,
    ConversationHandler
)
from dotenv import load_dotenv
from src.config import TOKEN
from src.keyboards import main_menu_keyboard
from src.handlers import (
    start_handler,
    ask_question_handler,
    button_click_handler,
    reset_progress_handler
)
from src.session_manager import end_session
from src.word_management import (
    add_word,
    save_word,
    delete_word,
    confirm_delete,
    show_user_words,
    handle_choice,
    handle_delete_choice,
    WAITING_WORD,
    WAITING_DELETE,
    WAITING_CHOICE,
    WAITING_DELETE_CHOICE
)
from src.stats import stats_handler

# ================== Настройка окружения ==================
load_dotenv()

# ================== Конфигурация логирования ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Главная функция для запуска бота"""
    # Инициализация бота
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # ================== Базовые обработчики ==================
    init_base_handlers(dispatcher)

    # ================== Обработчики главного меню ==================
    init_menu_handlers(dispatcher)

    # ================== Обработчики диалогов ==================
    init_conversation_handler(dispatcher)

    # ================== Обработка ошибок ==================
    dispatcher.add_error_handler(handle_errors)

    # Запуск бота
    updater.start_polling()
    logger.info("✅ Бот успешно запущен!")
    updater.idle()


def init_base_handlers(dispatcher):
    """Инициализация базовых обработчиков"""
    dispatcher.add_handler(CommandHandler("start", start_handler))
    dispatcher.add_handler(CallbackQueryHandler(reset_progress_handler, pattern="^reset_progress$"))
    dispatcher.add_handler(CallbackQueryHandler(button_click_handler))


def init_menu_handlers(dispatcher):
    """Инициализация обработчиков главного меню"""
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Начать тест 🚀$"), ask_question_handler))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Мои слова 📖$"), show_user_words))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Ваша статистика 📊$"), stats_handler))


def init_conversation_handler(dispatcher):
    """Инициализация ConversationHandler для управления диалогами"""
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(r"^Добавить слово ➕$"), add_word),
            MessageHandler(Filters.regex(r"^Удалить слово ➖$"), delete_word)
        ],
        states={
            WAITING_WORD: [MessageHandler(Filters.text & ~Filters.command, save_word)],
            WAITING_DELETE: [MessageHandler(Filters.text & ~Filters.command, confirm_delete)],
            WAITING_CHOICE: [MessageHandler(Filters.text & ~Filters.command, handle_choice)],
            WAITING_DELETE_CHOICE: [MessageHandler(Filters.text & ~Filters.command, handle_delete_choice)]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_action)
        ],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END
        }
    )
    dispatcher.add_handler(conv_handler)

    # Обработчик для выхода в главное меню
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^В меню ↩️$"), end_session))


def cancel_action(update, context):
    """Обработка команды отмены"""
    update.message.reply_text(
        "❌ Действие отменено",
        reply_markup=main_menu_keyboard()
    )
    return ConversationHandler.END


def handle_errors(update, context):
    """Обработка ошибок"""
    logger.error(f"Ошибка: {context.error}")


if __name__ == "__main__":
    main()
