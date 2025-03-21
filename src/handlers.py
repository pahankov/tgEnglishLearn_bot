import os
import random
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import CallbackContext, ConversationHandler
from src import db
from src.quiz import QuizManager
from src.keyboards import main_menu_keyboard, answer_keyboard, session_keyboard, send_pronounce_button, \
    add_more_keyboard, delete_more_keyboard
from src.sberspeech_api import SberSpeechAPI
from src.word_management import WAITING_WORD, WAITING_CHOICE, WAITING_DELETE, WAITING_DELETE_CHOICE, pluralize_words
from src.yandex_api import YandexDictionaryApi
from dotenv import load_dotenv
from src.session_manager import check_session_timeout
from datetime import datetime
from src.session_manager import save_session_data

load_dotenv()
logger = logging.getLogger(__name__)
quiz = QuizManager(db)

YANDEX_API_KEY = os.getenv("YANDEX_DICTIONARY_API_KEY")
if not YANDEX_API_KEY:
    raise ValueError("Ключ API Яндекс.Словаря не найден.")
yandex_api = YandexDictionaryApi(api_key=YANDEX_API_KEY)





def delete_active_keyboard(update: Update, context: CallbackContext):
    """
    Отправляет сообщение с ReplyKeyboardRemove для принудительного удаления активной клавиатуры.
    """
    update.message.reply_text("⏳ Очистка интерфейса...", reply_markup=ReplyKeyboardRemove())


# ================== Обработчики для главного меню и сессии ==================

def start_handler(update: Update, context: CallbackContext):
    user = update.effective_user
    if not db.get_user(user.id):
        db.create_user(user.id, user.username, user.first_name)
        logger.info(f"Создан пользователь: {user.first_name} (ID: {user.id})")
    else:
        logger.info(f"Пользователь {user.first_name} (ID: {user.id}) уже существует")
    update.message.reply_text(
        f"Привет, {user.first_name}! Я помогу тебе учить английский.",
        reply_markup=main_menu_keyboard()
    )


def ask_question_handler(update: Update, context: CallbackContext):
    """Генерация нового вопроса и управление сессией."""
    user_id = update.effective_user.id

    # Перед началом выполняем очистку интерфейса
    update.effective_message.reply_text("⏳ Очищаем предыдущий интерфейс...", reply_markup=ReplyKeyboardRemove())

    if 'active_session' not in context.user_data or not context.user_data['active_session']:
        update.effective_message.reply_text(
            "Сессия началась!",
            reply_markup=session_keyboard()
        )
        # Отправляем кнопку "Произношение слова 🔊" один раз
        send_pronounce_button(update.effective_chat.id, context)
        session_start = datetime.now()
        context.user_data.update({
            'session_start': session_start,
            'correct_answers': 0,
            'active_session': True,
            'job': None
        })
        job = context.job_queue.run_once(
            callback=check_session_timeout,
            when=900,
            context={
                'user_id': user_id,
                'session_start': session_start.timestamp()
            },
            name=str(user_id)
        )
        context.user_data['job'] = job

    # Обновляем таймер
    if 'job' in context.user_data:
        try:
            context.user_data['job'].schedule_removal()
        except Exception as e:
            logger.error(f"Ошибка удаления задачи: {e}")

    new_job = context.job_queue.run_once(
        callback=check_session_timeout,
        when=900,
        context={
            'user_id': user_id,
            'session_start': context.user_data['session_start'].timestamp()
        },
        name=str(user_id)
    )
    context.user_data['job'] = new_job

    # Получение следующего вопроса
    question = quiz.get_next_question(user_id)
    if not question:
        if context.user_data.get('active_session'):
            save_session_data(user_id, context)
            context.user_data.clear()
            keyboard = [[InlineKeyboardButton("Начать заново 🔄", callback_data="reset_progress")]]
            context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🎉 Вы изучили все слова! Отличная работа!",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        return

    try:
        word_en, word_ru, word_type, word_id = question
    except Exception as e:
        logger.error(f"Ошибка распаковки данных вопроса: {e}")
        return

    wrong_answers = list({
        ans.lower()
        for ans in quiz.get_wrong_answers(word_ru)
        if ans.lower() != word_ru.lower()
    })[:3]
    options = [word_ru.capitalize()] + [ans.capitalize() for ans in wrong_answers]
    random.shuffle(options)

    context.user_data["current_question"] = {
        "word_en": word_en,
        "correct_answer": word_ru.capitalize(),
        "word_id": word_id,
        "word_type": word_type,
        "options": options
    }

    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Переведи слово: *{word_en.capitalize()}*",
        parse_mode="Markdown",
        reply_markup=answer_keyboard(options)
    )


def reset_progress_handler(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    try:
        with db.conn:
            db.cur.execute("DELETE FROM user_progress WHERE user_id = %s", (user_id,))
        update.callback_query.answer("✅ Прогресс сброшен!")
        ask_question_handler(update, context)
    except Exception as e:
        logger.error(f"Ошибка сброса: {e}")
        update.callback_query.answer("❌ Ошибка!")


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
    current_question = context.user_data["current_question"]
    correct_answer = current_question["correct_answer"]
    word_id = current_question["word_id"]
    word_type = current_question["word_type"]
    user_id = update.effective_user.id

    if user_answer.lower() == correct_answer.lower():
        if not db.check_word_progress(user_id, word_id, word_type):
            session_start = context.user_data.get("session_start")
            quiz.mark_word_seen(user_id, word_id, word_type, session_start)
        del context.user_data["current_question"]
        query.answer(quiz.get_correct_response())

        try:
            context.bot.delete_message(chat_id=query.message.chat.id, message_id=query.message.message_id)
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения: {e}")

        ask_question_handler(update, context)
    else:
        options = current_question["options"]
        random.shuffle(options)
        try:
            query.edit_message_reply_markup(reply_markup=answer_keyboard(options))
        except Exception as e:
            logger.warning(f"Ошибка обновления клавиатуры: {e}")
        query.answer(quiz.get_incorrect_response())



# ================== Обработчики для управления словами (ConversationHandler) ==================

def add_word(update: Update, context: CallbackContext) -> int:
    """Начало процесса добавления слова."""
    update.message.reply_text(
        "⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove()
    )
    update.message.reply_text(
        "📝 Введите слово на русском языке:",
        reply_markup=add_more_keyboard()
    )
    return WAITING_WORD

def save_word_handler(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    input_text = update.message.text.strip().lower()

    if len(input_text.split()) > 1:
        update.message.reply_text("❌ Введите только ОДНО слово!", reply_markup=main_menu_keyboard())
        return WAITING_WORD

    if not re.match(r'^[а-яё\-]+$', input_text):
        update.message.reply_text("❌ Используйте только русские буквы и дефис.", reply_markup=main_menu_keyboard())
        return WAITING_WORD

    if db.check_duplicate(user_id, input_text):
        update.message.reply_text(
            f"❌ Слово '{input_text}' уже существует в базе!",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    try:
        api_response = yandex_api.lookup(input_text, "ru-en")
        if not api_response or not api_response.get('def'):
            update.message.reply_text("❌ Перевод не найден.", reply_markup=main_menu_keyboard())
            return WAITING_WORD

        first_translation = api_response['def'][0]['tr'][0]['text'].lower()
    except Exception as e:
        logger.error(f"Ошибка перевода: {e}")
        update.message.reply_text("❌ Ошибка обработки перевода.", reply_markup=main_menu_keyboard())
        return WAITING_WORD

    if db.check_duplicate(user_id, first_translation):
        update.message.reply_text(
            f"❌ Перевод '{first_translation}' уже существует!",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    if db.add_user_word(user_id, first_translation, input_text):
        count = db.count_user_words(user_id)
        update.message.reply_text(
            f"✅ Слово '{input_text}' успешно добавлено!\nВсего слов: {count}",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text("❌ Не удалось добавить слово.", reply_markup=main_menu_keyboard())

    return ConversationHandler.END

def handle_choice(update: Update, context: CallbackContext) -> int:
    """Обработка выбора после добавления."""
    update.message.reply_text(
        "⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove()
    )
    choice = update.message.text
    if choice == "Добавить ещё ➕":
        update.message.reply_text(
            "📝 Введите следующее слово:",
            reply_markup=add_more_keyboard()
        )
        return WAITING_WORD
    elif choice == "В меню ↩️":
        update.message.reply_text(
            "🏠 Возвращаемся в главное меню:",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "❌ Используйте кнопки для выбора!",
            reply_markup=add_more_keyboard()
        )
        return WAITING_CHOICE

def delete_word(update: Update, context: CallbackContext) -> int:
    """Начало процесса удаления слова."""
    update.message.reply_text(
        "⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove()
    )
    update.message.reply_text(
        "🗑 Введите слово для удаления (русское или английское):",
        reply_markup=delete_more_keyboard()
    )
    return WAITING_DELETE

def confirm_delete(update: Update, context: CallbackContext) -> int:
    """Обработка удаления и предложение продолжить."""
    update.message.reply_text(
        "⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove()
    )
    user_id = update.effective_user.id
    word = update.message.text.strip().lower()

    if db.delete_user_word(user_id, word):
        update.message.reply_text(
            f"✅ Слово/перевод '{word}' успешно удалено!",
            reply_markup=delete_more_keyboard()
        )
        return WAITING_DELETE_CHOICE
    else:
        update.message.reply_text(
            f"❌ Слово '{word}' не найдено в вашем словаре!",
            reply_markup=delete_more_keyboard()
        )
        return WAITING_DELETE_CHOICE

def handle_delete_choice(update: Update, context: CallbackContext) -> int:
    """Обработка выбора после удаления слова."""
    update.message.reply_text(
        "⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove()
    )
    choice = update.message.text
    if choice == "Удалить ещё ➖":
        update.message.reply_text(
            "🗑 Введите следующее слово для удаления:",
            reply_markup=delete_more_keyboard()
        )
        return WAITING_DELETE
    elif choice == "В меню ↩️":
        update.message.reply_text(
            "🏠 Возвращаемся в главное меню:",
            reply_markup=main_menu_keyboard()
        )
        return ConversationHandler.END
    else:
        update.message.reply_text(
            "❌ Используйте кнопки для выбора!",
            reply_markup=delete_more_keyboard()
        )
        return WAITING_DELETE_CHOICE


def show_user_words(update: Update, context: CallbackContext):
    """Отображение списка пользовательских слов."""
    update.message.reply_text(
        "⏳ Очищаем интерфейс...",
        reply_markup=ReplyKeyboardRemove()
    )
    user_id = update.effective_user.id
    try:
        words = db.get_user_words(user_id)
        if not words:
            update.message.reply_text(
                "📭 Ваш словарь пока пуст!",
                reply_markup=main_menu_keyboard()
            )
            return

        formatted = [f"• {en.capitalize()} - {ru.capitalize()}" for en, ru in words]
        count = len(words)
        update.message.reply_text(
            f"📖 Ваши слова ({count} {pluralize_words(count)}):\n" + "\n".join(formatted),
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logger.error(f"Ошибка показа слов: {str(e)}")
        update.message.reply_text(
            "❌ Ошибка при загрузке слов!",
            reply_markup=main_menu_keyboard()
        )

def pronounce_word_handler(update: Update, context: CallbackContext):
    logger.info("Функция pronounce_word_handler вызвана.")
    query = update.callback_query
    query.answer()

    # Проверка текущего вопроса
    current_question = context.user_data.get("current_question")
    if not current_question or "word_en" not in current_question:
        logger.warning("Не удалось найти слово для озвучивания.")
        query.answer("❌ Слово не найдено для произношения.", show_alert=True)
        return

    word = current_question["word_en"]
    try:
        sber_speech = SberSpeechAPI()
        audio_file = sber_speech.synthesize_text(word)
        if audio_file:
            context.bot.send_audio(chat_id=query.message.chat.id, audio=open(audio_file, "rb"))
            logger.info(f"Слово '{word}' успешно озвучено.")
        else:
            logger.error("Ошибка синтеза аудио.")
            query.answer("❌ Произошла ошибка при озвучивании слова.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в pronounce_word_handler: {e}")
        query.answer("❌ Возникла ошибка при обработке запроса.", show_alert=True)

def handle_menu_button(update: Update, context: CallbackContext):
    """Обработчик кнопки 'В меню' для всех состояний"""
    user_id = update.effective_user.id

    # Если активна сессия, сохраняем данные
    if 'active_session' in context.user_data:
        save_session_data(user_id, context)
        context.user_data.clear()

    # Удаляем клавиатуру
    update.message.reply_text(
        "⏳ Возвращаемся в главное меню...",
        reply_markup=ReplyKeyboardRemove()
    )

    # Отправляем главное меню
    update.message.reply_text(
        "🏠 Главное меню:",
        reply_markup=main_menu_keyboard()
    )

    # Завершаем все состояния ConversationHandler
    return ConversationHandler.END