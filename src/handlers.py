# handlers.py
import random
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from src.database import Database
from src.quiz import QuizManager
from src.keyboards import main_menu_keyboard, answer_keyboard
from src.word_management import add_word, save_word, delete_word, confirm_delete, show_user_words, WAITING_WORD, WAITING_DELETE

logger = logging.getLogger(__name__)

# Инициализируем базу и QuizManager
db = Database()
quiz = QuizManager(db)

def start_handler(update: Update, context: CallbackContext):
    user = update.effective_user
    if not db.get_user(user.id):
        db.create_user(user.id, user.username, user.first_name)
    update.message.reply_text(
        f"Привет, {user.first_name}! Я помогу тебе учить английский.",
        reply_markup=main_menu_keyboard()
    )

def ask_question_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    question = quiz.get_next_question(user_id)
    if not question:
        # Если все слова изучены – предлагаем сбросить прогресс
        keyboard = [[InlineKeyboardButton("Начать заново 🔄", callback_data="reset_progress")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎉 Вы изучили все слова! Отличная работа!",
            reply_markup=reply_markup
        )
        return

    word_en, word_ru, word_type, word_id = question
    wrong_answers = quiz.get_wrong_answers(word_ru)
    options = [word_ru] + wrong_answers
    random.shuffle(options)
    reply_markup = answer_keyboard(options)
    context.user_data["current_question"] = {
        "word_en": word_en,
        "correct_answer": word_ru,
        "word_id": word_id,
        "word_type": word_type,
        "options": options,
        "reply_markup": reply_markup
    }
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Переведи слово: *{word_en}*",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

def reset_progress_handler(update: Update, context: CallbackContext):
    """Очищает записи о прогрессе и начинает тест заново."""
    user_id = update.effective_user.id
    logger.info(f"reset_progress вызван для user_id: {user_id}")
    try:
        db.cur.execute("DELETE FROM user_progress WHERE user_id = %s", (user_id,))
        db.conn.commit()
        row_count = db.cur.rowcount
        logger.info(f"Прогресс сброшен для user_id {user_id}: удалено записей: {row_count}")
        update.callback_query.answer("Прогресс сброшен! Давайте начнем заново.")
        ask_question_handler(update, context)
    except Exception as e:
        logger.error(f"Ошибка при сбросе прогресса для user_id {user_id}: {e}")
        db.conn.rollback()
        update.callback_query.answer("Ошибка при сбросе прогресса. Попробуйте снова.")

def button_click_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    if "current_question" not in context.user_data:
        query.answer("❌ Сессия устарела. Начните новый тест.")
        return

    data = query.data.split("_")
    if len(data) < 2:
        query.answer("Некорректный ответ.")
        return
    user_answer = data[1]
    correct_answer = context.user_data["current_question"]["correct_answer"]
    word_id = context.user_data["current_question"]["word_id"]
    word_type = context.user_data["current_question"]["word_type"]

    if user_answer == correct_answer:
        response_text = quiz.get_correct_response()
        query.answer(response_text)
        quiz.mark_word_seen(query.from_user.id, word_id, word_type)
        del context.user_data["current_question"]
        ask_question_handler(update, context)
    else:
        response_text = quiz.get_incorrect_response()
        query.answer(response_text)
        # Обновляем клавиатуру для новой попытки
        options = context.user_data["current_question"]["options"]
        random.shuffle(options)
        reply_markup = answer_keyboard(options)
        try:
            query.edit_message_reply_markup(reply_markup=reply_markup)
        except Exception as e:
            logger.warning("Не удалось обновить клавиатуру.", exc_info=e)

def cancel_handler(update: Update, context: CallbackContext):
    update.message.reply_text("Действие отменено.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END
