import logging
from telegram import ReplyKeyboardRemove
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
    pronounce_word_handler,
    handle_menu_button
)
from src.stats import stats_handler, clear_user_sessions
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
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # ================== Регистрация обработчиков ==================

    # 1. Глобальные обработчики с максимальным приоритетом
    dispatcher.add_handler(CommandHandler("start", start_handler))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^В меню ↩️$"), handle_menu_button))

    # 2. ConversationHandlers
    add_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(r"^Добавить слово ➕$"), add_word)],
        states={
            WAITING_WORD: [MessageHandler(Filters.text & ~Filters.command, save_word)],
            WAITING_CHOICE: [MessageHandler(Filters.regex(r"^(Добавить ещё ➕|В меню ↩️)$"), handle_choice)]
        },
        fallbacks=[],
        allow_reentry=True,
        per_user=True
    )

    delete_conv = ConversationHandler(
        entry_points=[MessageHandler(Filters.regex(r"^Удалить слово ➖$"), delete_word)],
        states={
            WAITING_DELETE: [MessageHandler(Filters.text & ~Filters.command, confirm_delete)],
            WAITING_DELETE_CHOICE: [MessageHandler(Filters.regex(r"^(Удалить ещё ➖|В меню ↩️)$"), handle_delete_choice)]
        },
        fallbacks=[],
        allow_reentry=True,
        per_user=True
    )

    dispatcher.add_handler(add_conv)
    dispatcher.add_handler(delete_conv)

    # 3. Обработчики главного меню
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Начать тест 🚀$"), ask_question_handler))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Мои слова 📖$"), show_user_words))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Ваша статистика 📊$"), stats_handler))

    # 4. Обработчик кнопки "Очистить 🗑"
    dispatcher.add_handler(MessageHandler(
        Filters.regex(r"^Очистить 🗑$"),
        lambda update, context: clear_user_sessions(update, context)
    ))

    # 5. CallbackQuery обработчики
    dispatcher.add_handler(CallbackQueryHandler(button_click_handler, pattern=r"^answer_"))
    dispatcher.add_handler(CallbackQueryHandler(pronounce_word_handler, pattern="^pronounce_word$"))

    # 6. Обработка ошибок
    dispatcher.add_error_handler(lambda u, c: logger.error(f"Ошибка: {c.error}"))

    # Запуск бота
    updater.start_polling()
    logger.info("✅ Бот успешно запущен!")
    updater.idle()


if __name__ == "__main__":
    main()