# keyboards.py
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

def answer_keyboard(options):
    """
    Формирует inline-клавиатуру из списка вариантов ответа.
    Каждый ряд содержит по 2 кнопки.
    """
    keyboard = []
    for i in range(0, len(options), 2):
        row = []
        for opt in options[i:i + 2]:
            row.append(InlineKeyboardButton(opt, callback_data=f"answer_{opt}"))
        keyboard.append(row)
    return InlineKeyboardMarkup(keyboard)
