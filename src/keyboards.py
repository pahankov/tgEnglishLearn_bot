from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

# Клавиатура главного меню
def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Начать тест 🚀"), KeyboardButton("Добавить слово ➕")],
            [KeyboardButton("Удалить слово ➖"), KeyboardButton("Мои слова 📖")],
            [KeyboardButton("Ваша статистика 📊")]
        ],
        resize_keyboard=True
    )

# Клавиатура для добавления нового слова
def add_more_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Добавить ещё ➕"), KeyboardButton("В меню ↩️")]
        ],
        resize_keyboard=True
    )

# Клавиатура для удаления слова
def delete_more_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Удалить ещё ➖"), KeyboardButton("В меню ↩️")]
        ],
        resize_keyboard=True
    )

# Инлайновая клавиатура для выбора ответа
def answer_keyboard(options):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(opt, callback_data=f"answer_{opt}") for opt in options[i:i + 2]]
            for i in range(0, len(options), 2)
        ]
    )

# Клавиатура для активной сессии
def session_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton("В меню ↩️")]],
        resize_keyboard=True
    )

# Клавиатура для статистики
def stats_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton("Очистить 🗑"), KeyboardButton("В меню ↩️")]
        ],
        resize_keyboard=True
    )

def send_pronounce_button(chat_id, context):
    """Отправка кнопки 'Произношение слова 🔊'."""
    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("Произношение слова 🔊", callback_data="pronounce_word")]
    ])
    context.bot.send_message(chat_id, "Вы можете прослушать произношение слова здесь:", reply_markup=button)
