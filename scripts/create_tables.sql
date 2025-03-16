CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(50),
    first_name VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS common_words (
    id SERIAL PRIMARY KEY,
    english_word VARCHAR(50),
    russian_translation VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS user_words (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    english_word VARCHAR(50),
    russian_translation VARCHAR(50),
    UNIQUE (user_id, english_word)
);

CREATE TABLE IF NOT EXISTS user_progress (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    word_id INT,
    word_type VARCHAR(50),
    UNIQUE(user_id, word_id, word_type)
);

CREATE TABLE IF NOT EXISTS session_stats (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(user_id),
    session_date TIMESTAMP NOT NULL,
    learned_words INT NOT NULL,
    session_duration INT NOT NULL
);