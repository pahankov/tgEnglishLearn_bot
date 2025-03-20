import os
import random
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from src import db
from src.quiz import QuizManager
from src.keyboards import main_menu_keyboard, answer_keyboard, session_keyboard, send_pronounce_button
from src.sberspeech_api import SberSpeechAPI
from src.word_management import  WAITING_WORD
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

    # Проверяем, началась ли уже сессия
    if 'active_session' not in context.user_data or not context.user_data['active_session']:
        update.effective_message.reply_text(
            "Сессия началась!",
            reply_markup=session_keyboard()
        )

        # Инициализируем данные сессии
        session_start = datetime.now()
        context.user_data.update({
            'session_start': session_start,
            'correct_answers': 0,
            'active_session': True,
            'job': None
        })

        # Запускаем таймер с передачей session_start в контекст
        job = context.job_queue.run_once(
            callback=check_session_timeout,
            when=900,
            context={
                'user_id': user_id,
                'session_start': session_start.timestamp()  # Сохраняем как timestamp
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

    # Создаем новый таймер с актуальным session_start
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

    # ... остальная логика ...

    # Получение следующего вопроса
    question = quiz.get_next_question(user_id)
    if not question:
        # Если вопросы закончились
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

    # Формирование вариантов ответа
    wrong_answers = list({
        ans.lower()
        for ans in quiz.get_wrong_answers(word_ru)
        if ans.lower() != word_ru.lower()
    })[:3]

    options = [word_ru.capitalize()] + [ans.capitalize() for ans in wrong_answers]
    random.shuffle(options)

    # Сохранение текущего вопроса в контексте пользователя
    context.user_data["current_question"] = {
        "word_en": word_en,
        "correct_answer": word_ru.capitalize(),
        "word_id": word_id,
        "word_type": word_type,
        "options": options
    }

    # Отправка вопроса пользователю
    context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Переведи слово: *{word_en.capitalize()}*",
        parse_mode="Markdown",
        reply_markup=answer_keyboard(options)
    )
    # Отправка кнопки "Произношение слова 🔊" отдельно
    send_pronounce_button(update.effective_chat.id, context)

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

    # Проверка регистра
    if user_answer.lower() == correct_answer.lower():
        if not db.check_word_progress(user_id, word_id, word_type):
            # Передаём session_start из контекста
            session_start = context.user_data.get("session_start")
            logger.info(f"[DEBUG] session_start в button_click: {session_start}")  # Логирование
            quiz.mark_word_seen(user_id, word_id, word_type, session_start)
        del context.user_data["current_question"]
        query.answer(quiz.get_correct_response())
        ask_question_handler(update, context)
    else:
        options = current_question["options"]
        random.shuffle(options)
        try:
            query.edit_message_reply_markup(reply_markup=answer_keyboard(options))
        except Exception as e:
            logger.warning(f"Ошибка обновления клавиатуры: {e}")
        query.answer(quiz.get_incorrect_response())

def save_word_handler(update: Update, context: CallbackContext) -> int:
    user_id = update.effective_user.id
    input_text = update.message.text.strip().lower()

    # Проверка на количество слов
    if len(input_text.split()) > 1:
        update.message.reply_text("❌ Введите только ОДНО слово!", reply_markup=main_menu_keyboard())
        return WAITING_WORD

    # Проверка на допустимые символы (русские буквы и дефис)
    if not re.match(r'^[а-яё\-]+$', input_text):
        update.message.reply_text("❌ Используйте только русские буквы и дефис.", reply_markup=main_menu_keyboard())
        return WAITING_WORD

    # Проверка существования слова в общих или пользовательских словарях
    if db.check_duplicate(user_id, input_text):
        update.message.reply_text(
            f"❌ Слово '{input_text}' уже существует в базе!",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    # Получение перевода
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

    # Проверка дубликатов перевода
    if db.check_duplicate(user_id, first_translation):
        update.message.reply_text(
            f"❌ Перевод '{first_translation}' уже существует!",
            reply_markup=main_menu_keyboard()
        )
        return WAITING_WORD

    # Добавление слова
    if db.add_user_word(user_id, first_translation, input_text):
        count = db.count_user_words(user_id)
        update.message.reply_text(
            f"✅ Слово '{input_text}' успешно добавлено!\nВсего слов: {count}",
            reply_markup=main_menu_keyboard()
        )
    else:
        update.message.reply_text("❌ Не удалось добавить слово.", reply_markup=main_menu_keyboard())

    return ConversationHandler.END





def pronounce_word_handler(update: Update, context: CallbackContext):
    """Обработка кнопки 'Произношение слова 🔊'."""
    query = update.callback_query
    query.answer()  # Обязательно отвечаем на callback

    # Получаем слово из текущего вопроса
    current_question = context.user_data.get("current_question")
    if not current_question or "word_en" not in current_question:
        query.answer("❌ Не удалось найти слово для озвучивания.", show_alert=True)
        return

    word = current_question["word_en"]  # Слово для произношения
    sber_speech = SberSpeechAPI()

    # Синтезируем произношение
    audio_file = sber_speech.synthesize_text(word)
    if audio_file:
        # Отправляем озвучку пользователю
        context.bot.send_audio(chat_id=query.message.chat.id, audio=open(audio_file, "rb"))
    else:
        query.answer("❌ Произошла ошибка при озвучивании слова.", show_alert=True)

