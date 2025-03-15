from telegram import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup

def main_menu_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Начать тест 🚀"), KeyboardButton("Добавить слово ➕")],
            [KeyboardButton("Удалить слово ➖"), KeyboardButton("Мои слова 📖")],
            [KeyboardButton("Ваша статистика 📊")]
        ],
        resize_keyboard=True
    )

def add_more_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Добавить ещё ➕"), KeyboardButton("В меню ↩️")]
        ],
        resize_keyboard=True
    )

def answer_keyboard(options):
    keyboard = []
    for i in range(0, len(options), 2):
        row = [InlineKeyboardButton(opt, callback_data=f"answer_{opt}") for opt in options[i:i+2]]
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)

def delete_more_keyboard():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("Удалить ещё ➖"), KeyboardButton("В меню ↩️")]
        ],
        resize_keyboard=True
    )
