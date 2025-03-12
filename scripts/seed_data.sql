INSERT INTO common_words (english_word, russian_translation)
VALUES
('We', 'Мы'),
('She', 'Она'),
('Red', 'Красный'),
('Blue', 'Синий'),
('I', 'Я'),
('You', 'Ты'),
('Green', 'Зеленый'),
('Black', 'Черный'),
('They', 'Они'),
('It', 'Оно')
ON CONFLICT (english_word) DO NOTHING;
