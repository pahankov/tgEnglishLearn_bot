import os
import random
import logging
import re
import telegram
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove, ReplyKeyboardMarkup
from telegram.ext import CallbackContext, ConversationHandler
from src import db
from src.quiz import QuizManager
from src.keyboards import main_menu_keyboard, answer_keyboard,  send_pronounce_button, \
MENU_BUTTON
from src.sberspeech_api import SberSpeechAPI
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

def delete_bot_messages(update: Update, context: CallbackContext):
    """Удаление последних N сообщений бота в чате."""
    try:
        chat_id = update.effective_chat.id
        max_messages_to_check = 20  # Например, обрабатываем только последние 20 сообщений
        for message_id in range(update.message.message_id, update.message.message_id - max_messages_to_check, -1):
            try:
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except telegram.error.BadRequest as e:
                logger.warning(f"Ошибка удаления сообщения {message_id}: {e}")
    except Exception as e:
        logger.error(f"Не удалось очистить чат: {e}")





def ask_question_handler(update: Update, context: CallbackContext):
    """Генерация нового вопроса и управление сессией."""
    # Удаляем все сообщения бота перед началом
    delete_bot_messages(update, context)
    user_id = update.effective_user.id


    # Определяем клавиатуру с глобальной кнопкой "В меню ↩️"
    session_keyboard = ReplyKeyboardMarkup(
        [[MENU_BUTTON]],  # Используем глобальную переменную MENU_BUTTON
        resize_keyboard=True  # Чтобы клавиатура была компактной
    )

    # Если сессия ещё не начата
    if 'active_session' not in context.user_data or not context.user_data['active_session']:
        update.effective_message.reply_text(
            "Сессия началась!",
            reply_markup=session_keyboard  # Добавляем клавиатуру
        )
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

        # Отправляем и закрепляем кнопку "Произношение слова 🔊" только при старте сессии
        send_pronounce_button(update.effective_chat.id, context)

    # Логика обновления таймера
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
        reply_markup=answer_keyboard(options)  # Клавиатура с вариантами ответов
    )


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


def pronounce_word_handler(update: Update, context: CallbackContext):
    """Обработчик для воспроизведения произношения текущего слова."""
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
        # Подключение к API синтеза речи
        sber_speech = SberSpeechAPI()
        audio_file = sber_speech.synthesize_text(word)

        if audio_file:
            # Отправляем аудио с произношением
            with open(audio_file, "rb") as audio:
                context.bot.send_audio(chat_id=query.message.chat.id, audio=audio)
            logger.info(f"Слово '{word}' успешно озвучено.")
        else:
            logger.error("Ошибка синтеза аудио.")
            query.answer("❌ Произошла ошибка при озвучивании слова.", show_alert=True)

    except FileNotFoundError as e:
        logger.error(f"Аудиофайл не найден: {e}")
        query.answer("❌ Не удалось найти файл произношения.", show_alert=True)
    except Exception as e:
        logger.error(f"Ошибка в pronounce_word_handler: {e}")
        query.answer("❌ Возникла ошибка при обработке запроса.", show_alert=True)


def handle_menu_button(update: Update, context: CallbackContext):
    """Обработчик кнопки 'В меню' для завершения сессии."""
    user_id = update.effective_user.id
    logger.info(f"✅ Обработка нажатия кнопки 'В меню' для пользователя {user_id}.")

    # Проверка активной сессии
    if 'active_session' in context.user_data:
        logger.info(f"⏱ Сохранение данных активной сессии для пользователя {user_id}.")

        # Сохранение данных сессии
        try:
            save_session_data(user_id, context)
            logger.info(f"✅ Данные сессии успешно сохранены для пользователя {user_id}.")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения данных сессии: {e}")

    # Очистка данных пользователя
    logger.info(f"🗑 Очистка данных сессии для пользователя {user_id}.")
    if 'job' in context.user_data:
        try:
            context.user_data['job'].schedule_removal()
            logger.info(f"✅ Таймер успешно удален для пользователя {user_id}.")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка удаления задачи таймера: {e}")
        context.user_data.pop('job', None)

    # Удаление данных, связанных с сессией
    keys_to_remove = [
        'active_session',
        'current_state',
        'word',
        'translation',
        'current_question',
        'session_start',
        'correct_answers'
    ]
    for key in keys_to_remove:
        if key in context.user_data:
            context.user_data.pop(key, None)
            logger.debug(f"[DEBUG] Удален ключ '{key}' из user_data.")

    # Отправка главного меню
    try:
        update.message.reply_text(
            text="🏠 Главное меню:",
            reply_markup=main_menu_keyboard()
        )
        logger.info(f"✅ Пользователю {user_id} отправлено главное меню.")
    except Exception as e:
        logger.error(f"❌ Ошибка при отправке главного меню для пользователя {user_id}: {e}")

    # Возврат для явного завершения ConversationHandler
    return ConversationHandler.END
