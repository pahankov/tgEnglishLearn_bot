CREATE TABLE IF NOT EXISTS users (
    user_id BIGINT PRIMARY KEY,
    username VARCHAR(255),
    first_name VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS common_words (
    word_id SERIAL PRIMARY KEY,
    english_word VARCHAR(255) UNIQUE,
    russian_translation VARCHAR(255) UNIQUE
);

CREATE TABLE IF NOT EXISTS user_words (
    user_word_id SERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(user_id),
    english_word VARCHAR(255),
    russian_translation VARCHAR(255),
    UNIQUE(user_id, english_word)
);
