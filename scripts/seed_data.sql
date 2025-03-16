INSERT INTO common_words (english_word, russian_translation)
VALUES
('we', 'мы'),
('she', 'она'),
('red', 'красный'),
('blue', 'синий'),
('i', 'я'),
('you', 'ты'),
('green', 'зеленый'),
('black', 'черный'),
('they', 'они'),
('it', 'оно')
ON CONFLICT (LOWER(english_word), LOWER(russian_translation)) DO NOTHING;