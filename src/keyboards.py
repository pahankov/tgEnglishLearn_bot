from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

# Общая кнопка для возврата в меню
MENU_BUTTON = KeyboardButton("В меню ↩️")


def main_menu_keyboard():
    """Клавиатура для главного меню."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Начать тест 🚀")],
            [KeyboardButton("Удалить слово ➖"), KeyboardButton("Добавить слово ➕")],
            [KeyboardButton("Ваша статистика 📊"), KeyboardButton("Мои слова 📖")],
        ],
        resize_keyboard=True,
    )


def add_more_keyboard():
    """Клавиатура для добавления слов."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Добавить ещё ➕"), KeyboardButton("Назад ↩️")],
        ],
        resize_keyboard=True,
    )


def delete_more_keyboard():
    """Клавиатура для удаления слов."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Удалить ещё ➖"), KeyboardButton("Назад ↩️")],
        ],
        resize_keyboard=True,
    )


def session_keyboard():
    """Клавиатура для сессии."""
    return ReplyKeyboardMarkup(
        keyboard=[[MENU_BUTTON]],
        resize_keyboard=True,
    )


def stats_keyboard():
    """Клавиатура для статистики."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Очистить 🗑"), KeyboardButton("Назад ↩️")],
        ],
        resize_keyboard=True,
    )


def answer_keyboard(options):
    """Клавиатура с вариантами ответов."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(opt, callback_data=f"answer_{opt}") for opt in options[i : i + 2]]
            for i in range(0, len(options), 2)
        ]
    )


def send_pronounce_button(chat_id, context):
    """Отправка кнопки 'Произношение слова 🔊'."""
    button = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Произношение слова 🔊", callback_data="pronounce_word")]]
    )
    context.bot.send_message(
        chat_id, "Вы можете прослушать произношение слова здесь:", reply_markup=button
    )
