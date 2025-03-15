import requests
import logging

logger = logging.getLogger(__name__)

class YandexDictionaryApi:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://dictionary.yandex.net/api/v1/dicservice.json"

    def lookup(self, word, lang="en-ru"):
        """
        Выполняет запрос к Yandex Dictionary API для получения перевода слова.
        :param word: слово для перевода
        :param lang: направление перевода, по умолчанию "en-ru"
        :return: первый перевод (строка) или None, если перевод не найден
        """
        try:
            response = requests.get(f"{self.base_url}/lookup", params={"key": self.api_key, "text": word, "lang": lang})
            if response.status_code == 200:
                data = response.json()
                if "def" in data and data["def"]:  # Проверяем, есть ли переводы
                    # Берём первый найденный перевод
                    return data["def"][0]["tr"][0]["text"]
                else:
                    return None
            else:
                logger.error(f"Ошибка при запросе к API: {response.status_code}, {response.text}")
                return None
        except Exception as e:
            logger.error(f"Ошибка в YandexDictionaryApi.lookup: {e}")
            return None

import requests
import logging

logger = logging.getLogger(__name__)

class YandexDictionaryApi:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://dictionary.yandex.net/api/v1/dicservice.json"

    def get_langs(self):
        """
        Возвращает список направлений перевода, поддерживаемых API.
        """
        try:
            response = requests.get(f"{self.base_url}/getLangs", params={"key": self.api_key})
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Ошибка при запросе getLangs: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logger.error(f"Исключение в get_langs: {e}")
            return None

    def lookup(self, word, lang="en-ru"):
        """
        Выполняет перевод слова.
        :param word: слово, которое нужно перевести.
        :param lang: направление перевода, например, "en-ru".
        :return: Полный JSON-объект с переводом или None в случае ошибки.
        """
        try:
            response = requests.get(
                f"{self.base_url}/lookup",
                params={"key": self.api_key, "text": word, "lang": lang}
            )
            if response.status_code == 200:
                return response.json()  # Возвращаем JSON-объект вместо строки
            else:
                logger.error(f"Ошибка в lookup: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logger.error(f"Исключение в lookup: {e}")
            return None
