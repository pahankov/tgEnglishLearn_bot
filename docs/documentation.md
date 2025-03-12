## Схема БД
- **users** (user_id, username, first_name, created_at)
- **common_words** (word_id, english_word, russian_translation)
- **user_words** (user_word_id, user_id, english_word, russian_translation)

## Установка
1. Установите зависимости: `pip install -r requirements.txt`.
2. Создайте БД: выполните `create_tables.sql`.
3. Заполните общие слова: выполните `seed_data.sql`.
4. Запустите бота: `python src/bot.py`.
