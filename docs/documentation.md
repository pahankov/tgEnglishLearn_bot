# Документация по использованию программы `tgEnglishLearn_bot`

## Описание проекта

`tgEnglishLearn_bot` — это Telegram-бот для изучения английского языка. Бот позволяет пользователям добавлять новые слова в свой словарь, удалять их, проходить тесты на знание слов, а также отслеживать свой прогресс через статистику. Бот использует API Яндекс.Словаря для перевода слов и SberSpeech API для озвучивания произношения.

## Установка и настройка

### 1. Установка зависимостей

Для работы бота необходимо установить зависимости, указанные в файле `requirements.txt`. Выполните следующую команду в терминале:

```bash
pip install -r requirements.txt
```

### 2. Настройка переменных окружения

Для корректной работы бота необходимо настроить переменные окружения. Создайте файл `.env` в корневой директории проекта и добавьте в него следующие переменные:

```plaintext
TOKEN=ваш_токен_бота
DB_NAME=имя_базы_данных
DB_USER=пользователь_базы_данных
DB_PASSWORD=пароль_базы_данных
DB_HOST=хост_базы_данных
YANDEX_DICTIONARY_API_KEY=ваш_ключ_API_Яндекс.Словаря
SBER_CLIENT_ID=ваш_client_id_SberSpeech
SBER_CLIENT_SECRET=ваш_client_secret_SberSpeech
```

### 3. Настройка базы данных

Перед запуском бота необходимо создать и настроить базу данных. В проекте используются SQL-скрипты для создания таблиц и заполнения их начальными данными.

1. Создайте базу данных PostgreSQL с именем, указанным в переменной окружения `DB_NAME`.
2. Запустите скрипт `create_tables.sql` для создания необходимых таблиц:

```bash
psql -U ваш_пользователь -d имя_базы_данных -a -f scripts/create_tables.sql
```

3. Запустите скрипт `seed_data.sql` для заполнения таблицы `common_words` начальными данными:

```bash
psql -U ваш_пользователь -d имя_базы_данных -a -f scripts/seed_data.sql
```

### 4. Запуск бота

После настройки всех зависимостей и переменных окружения, запустите бота с помощью команды:

```bash
python main.py
```

## Использование бота

### 1. Команды бота

- **/start** — запуск бота и отображение главного меню.
- **Начать тест 🚀** — начать тест на знание слов.
- **Добавить слово ➕** — добавить новое слово в словарь.
- **Удалить слово ➖** — удалить слово из словаря.
- **Мои слова 📖** — просмотреть список добавленных слов.
- **Ваша статистика 📊** — просмотреть статистику изучения слов.
- **Очистить 🗑** — очистить статистику сессий.

### 2. Добавление слов

1. Нажмите кнопку **Добавить слово ➕**.
2. Введите слово на русском языке.
3. Бот автоматически переведёт слово на английский и добавит его в ваш словарь.
4. После добавления слова вы можете продолжить добавлять новые слова или вернуться в главное меню.

### 3. Удаление слов

1. Нажмите кнопку **Удалить слово ➖**.
2. Введите слово на русском или английском языке, которое хотите удалить.
3. Бот удалит слово из вашего словаря, если оно существует.
4. После удаления вы можете продолжить удалять слова или вернуться в главное меню.

### 4. Тестирование

1. Нажмите кнопку **Начать тест 🚀**.
2. Бот будет задавать вопросы на перевод слов.
3. Выберите правильный вариант перевода из предложенных.
4. После завершения теста бот покажет ваш прогресс и предложит начать новый тест.

### 5. Просмотр статистики

1. Нажмите кнопку **Ваша статистика 📊**.
2. Бот покажет количество изученных и добавленных слов, а также график прогресса по сессиям.
3. Вы можете очистить статистику сессий, нажав кнопку **Очистить 🗑**.

### 6. Просмотр списка слов

1. Нажмите кнопку **Мои слова 📖**.
2. Бот покажет список всех добавленных вами слов с их переводами.

## Архитектура проекта

### Основные модули

- **main.py** — главный файл для запуска бота.
- **handlers.py** — обработчики команд и сообщений.
- **keyboards.py** — клавиатуры для взаимодействия с пользователем.
- **database.py** — модуль для работы с базой данных.
- **quiz.py** — логика тестирования пользователя.
- **session_manager.py** — управление сессиями пользователя.
- **stats.py** — обработка и отображение статистики.
- **word_management.py** — управление словами пользователя.
- **yandex_api.py** — взаимодействие с API Яндекс.Словаря.
- **sberspeech_api.py** — взаимодействие с SberSpeech API для синтеза речи.

### База данных

База данных состоит из следующих таблиц:

- **users** — информация о пользователях.
- **common_words** — общие слова для изучения.
- **user_words** — слова, добавленные пользователями.
- **user_progress** — прогресс пользователей по изучению слов.
- **session_stats** — статистика сессий пользователей.

## Логирование

Логирование осуществляется с помощью модуля `logging`. Логи записываются в стандартный вывод и содержат информацию о действиях пользователей, ошибках и других событиях.

## Заключение

`tgEnglishLearn_bot` предоставляет удобный интерфейс для изучения английского языка через Telegram. Бот позволяет пользователям добавлять и удалять слова, проходить тесты и отслеживать свой прогресс. Для работы бота требуется настройка базы данных и API-ключей для Яндекс.Словаря и SberSpeech.