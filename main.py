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
    reset_progress_handler,
    pronounce_word_handler,
    handle_menu_button  # Добавлен новый обработчик
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
from src.stats import stats_handler, clear_user_sessions

# ================== Настройка окружения ==================
load_dotenv()

# ================== Конфигурация логирования ==================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Главная функция для запуска бота."""
    # Инициализация бота
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # ================== Регистрация обработчиков ==================

    # 1. Глобальный обработчик кнопки "В меню" (должен быть ПЕРВЫМ!)
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^В меню ↩️$"), handle_menu_button))

    # 2. Обработчики команд
    dispatcher.add_handler(CommandHandler("start", start_handler))

    # 3. Обработчики для главного меню
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Начать тест 🚀$"), ask_question_handler))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Мои слова 📖$"), show_user_words))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Ваша статистика 📊$"), stats_handler))

    # 4. CallbackQuery обработчики
    dispatcher.add_handler(CallbackQueryHandler(reset_progress_handler, pattern="^reset_progress$"))
    dispatcher.add_handler(CallbackQueryHandler(button_click_handler, pattern=r"^answer_"))
    dispatcher.add_handler(CallbackQueryHandler(pronounce_word_handler, pattern="^pronounce_word$"))

    # 5. ConversationHandler для добавления слов
    dispatcher.add_handler(ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(r"^Добавить слово ➕$"), add_word)],
        states={
            WAITING_WORD: [
                MessageHandler(
                    Filters.text & ~Filters.regex(r"^В меню ↩️$") & ~Filters.command,
                    save_word
                )
            ],
            WAITING_CHOICE: [
                MessageHandler(
                    Filters.text & ~Filters.regex(r"^В меню ↩️$") & ~Filters.command,
                    handle_choice
                )
            ]
        },
        fallbacks=[],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    ))

    # 6. ConversationHandler для удаления слов
    dispatcher.add_handler(ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(r"^Удалить слово ➖$"), delete_word)],
        states={
            WAITING_DELETE: [
                MessageHandler(
                    Filters.text & ~Filters.regex(r"^В меню ↩️$") & ~Filters.command,
                    confirm_delete
                )
            ],
            WAITING_DELETE_CHOICE: [
                MessageHandler(
                    Filters.text & ~Filters.regex(r"^В меню ↩️$") & ~Filters.command,
                    handle_delete_choice
                )
            ]
        },
        fallbacks=[],
        map_to_parent={ConversationHandler.END: ConversationHandler.END}
    ))

    # 7. Обработка ошибок
    dispatcher.add_error_handler(handle_errors)

    # Запуск бота
    updater.start_polling()
    logger.info("✅ Бот успешно запущен!")
    updater.idle()


def handle_errors(update, context):
    """Обработка ошибок."""
    logger.error(f"Ошибка: {context.error}")


if __name__ == "__main__":
    main()