from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.error import BadRequest
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext,
    MessageHandler,
    Filters,
    ConversationHandler,
)
from src.database import Database
from src.config import TOKEN
import logging
import random
from src.word_management import (
    add_word,
    save_word,
    delete_word,
    confirm_delete,
    show_user_words,
    WAITING_WORD,
    WAITING_DELETE,
)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация базы данных
db = Database()

# Основное меню для общения с ботом
MAIN_MENU_KEYBOARD = ReplyKeyboardMarkup(
    [
        [KeyboardButton("Начать тест 🚀"), KeyboardButton("Добавить слово ➕")],
        [KeyboardButton("Удалить слово ➖"), KeyboardButton("Мои слова 📖")],
    ],
    resize_keyboard=True,
)


def start(update: Update, context: CallbackContext):
    """
    Обработчик команды /start.
    Регистрирует пользователя, если он ещё не существует, и отправляет приветственное сообщение.
    """
    user = update.effective_user
    if not db.get_user(user.id):
        db.create_user(user.id, user.username, user.first_name)
    update.message.reply_text(
        f"Привет, {user.first_name}! Я помогу тебе учить английский. 🎓",
        reply_markup=MAIN_MENU_KEYBOARD,
    )


def ask_question(update: Update, context: CallbackContext):
    """
    Выбирает и задаёт новый вопрос для пользователя.
    Если все слова изучены, предлагает сбросить прогресс через кнопку "Начать заново 🔄".
    """
    user_id = update.effective_user.id
    word_info = db.get_unseen_word(user_id)

    if not word_info:
        # Если все слова пройдены, выдаём сообщение и кнопку для сброса прогресса
        keyboard = [[InlineKeyboardButton("Начать заново 🔄", callback_data="reset_progress")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎉 Вы молодец! Вы изучили все доступные слова. Продолжайте в том же духе!",
            reply_markup=reply_markup,
        )
        return

    word_en, word_ru, word_type, word_id = word_info
    wrong_answers = db.get_wrong_translations(word_ru, 3)
    options = [word_ru] + wrong_answers
    random.shuffle(options)

    # Формируем клавиатуру с вариантами ответа
    keyboard = [
        [
            InlineKeyboardButton(options[i], callback_data=f"answer_{options[i]}"),
            InlineKeyboardButton(options[i + 1], callback_data=f"answer_{options[i + 1]}"),
        ]
        for i in range(0, len(options), 2)
    ]

    context.user_data["current_question"] = {
        "word_en": word_en,
        "correct_answer": word_ru,
        "word_id": word_id,
        "word_type": word_type,
        "options": options,
        "reply_markup": InlineKeyboardMarkup(keyboard),
    }

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Переведи слово: *{word_en}*",
        parse_mode="Markdown",
        reply_markup=context.user_data["current_question"]["reply_markup"],
    )


def reset_progress(update: Update, context: CallbackContext):
    """
    Обработчик нажатия кнопки "Начать заново 🔄".
    Очищает записи из user_progress для текущего пользователя и запускает новый тест.
    """
    user_id = update.effective_user.id
    logger.info(f"reset_progress вызван для user_id: {user_id}")
    try:
        db.cur.execute("DELETE FROM user_progress WHERE user_id = %s", (user_id,))
        db.conn.commit()
        row_count = db.cur.rowcount
        logger.info(f"Прогресс сброшен для user_id {user_id}: удалено записей: {row_count}")
        update.callback_query.answer("Прогресс сброшен! Давайте начнем заново.")
        ask_question(update, context)
    except Exception as e:
        logger.error(f"Ошибка при сбросе прогресса для user_id {user_id}: {e}")
        db.conn.rollback()
        update.callback_query.answer("Ошибка при сбросе прогресса. Попробуйте снова.")


def button_click(update: Update, context: CallbackContext):
    """
    Обрабатывает нажатия кнопок с вариантами ответов.
    При правильном ответе выдаёт разнообразное уведомление через query.answer() (по кругу) и обновляет прогресс.
    При неверном – выдаёт циклический ответ и обновляет варианты (клавиатуру) для новой попытки.
    """
    query = update.callback_query

    if "current_question" not in context.user_data:
        query.answer("❌ Сессия устарела. Начните новый тест.")
        return

    # Извлекаем введённый ответ и данные текущего вопроса
    user_answer = query.data.split("_")[1]
    correct_answer = context.user_data["current_question"]["correct_answer"]
    word_id = context.user_data["current_question"]["word_id"]
    word_type = context.user_data["current_question"]["word_type"]

    if user_answer == correct_answer:
        # Разнообразные уведомления для правильного ответа (циклически)
        correct_responses = [
            "✅ Отлично! Молодец! 🎉",
            "🌟 Верно, ты справился! 👍",
            "🔥 Правильно! Продолжай в том же духе!",
            "😎 Молодец! Ответ правильный!",
            "🎊 Замечательно, верно отвечено!",
        ]
        if "correct_index" not in context.user_data:
            context.user_data["correct_index"] = 0
        index = context.user_data["correct_index"]
        response_text = correct_responses[index]
        context.user_data["correct_index"] = (index + 1) % len(correct_responses)

        query.answer(response_text)
        db.mark_word_as_seen(query.from_user.id, word_id, word_type)
        del context.user_data["current_question"]
        ask_question(update, context)
    else:
        # Разнообразные уведомления для неверного ответа (циклические)
        incorrect_responses = [
            "❌ Попробуй ещё раз!",
            "😕 Неверно. Дай еще одну попытку!",
            "🚫 Ошибка. Попытайся снова!",
            "🙁 Не угадал. Попробуй ещё раз!",
            "😢 Неправильно. Давай, у тебя получится!",
        ]
        if "incorrect_index" not in context.user_data:
            context.user_data["incorrect_index"] = 0
        idx_incorrect = context.user_data["incorrect_index"]
        incorrect_text = incorrect_responses[idx_incorrect]
        context.user_data["incorrect_index"] = (idx_incorrect + 1) % len(incorrect_responses)

        query.answer(incorrect_text)
        # Обновляем варианты ответа (перемешиваем клавиатуру)
        current_question = context.user_data["current_question"]
        options = current_question["options"]
        random.shuffle(options)
        keyboard = []
        for i in range(0, len(options), 2):
            row = []
            for opt in options[i : i + 2]:
                callback_data = f"answer_{opt}_{random.randint(1, 1000)}"
                row.append(InlineKeyboardButton(opt, callback_data=callback_data))
            keyboard.append(row)
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            query.edit_message_reply_markup(reply_markup=reply_markup)
        except BadRequest:
            logger.warning("Сообщение не было изменено (дубликат).")


def cancel(update: Update, context: CallbackContext):
    """
    Обработчик отмены действий.
    """
    update.message.reply_text("Действие отменено.", reply_markup=MAIN_MENU_KEYBOARD)
    return ConversationHandler.END


def error_handler(update: Update, context: CallbackContext):
    """
    Глобальный обработчик ошибок.
    """
    logger.error(f"Ошибка: {context.error}", exc_info=context.error)
    if update.effective_message:
        update.effective_message.reply_text("⚠️ Произошла ошибка. Попробуйте снова.")


def main():
    """
    Основная функция. Регистрирует обработчики и запускает бота.
    """
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    # Сначала обработчик для сброса прогресса (при callback_data = "reset_progress")
    dispatcher.add_handler(CallbackQueryHandler(reset_progress, pattern="^reset_progress$"))
    # Затем общий обработчик ответов от inline кнопок
    dispatcher.add_handler(CallbackQueryHandler(button_click))

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Начать тест 🚀$"), ask_question))
    dispatcher.add_handler(MessageHandler(Filters.regex(r"^Мои слова 📖$"), show_user_words))

    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.regex(r"^Добавить слово ➕$"), add_word),
            MessageHandler(Filters.regex(r"^Удалить слово ➖$"), delete_word),
        ],
        states={
            WAITING_WORD: [MessageHandler(Filters.text & ~Filters.command, save_word)],
            WAITING_DELETE: [MessageHandler(Filters.text & ~Filters.command, confirm_delete)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    dispatcher.add_handler(conv_handler)
    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
