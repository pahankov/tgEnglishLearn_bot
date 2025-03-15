import requests
import logging

logger = logging.getLogger(__name__)


class YandexDictionaryApi:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://dictionary.yandex.net/api/v1/dicservice.json"

    def lookup(self, word: str, lang: str = "en-ru") -> dict | None:
        """
        Возвращает полный JSON-ответ API, как в первоначальной версии
        """
        try:
            response = requests.get(
                f"{self.base_url}/lookup",
                params={
                    "key": self.api_key,
                    "text": word,
                    "lang": lang
                },
                timeout=5
            )
            response.raise_for_status()
            return response.json()

        except requests.HTTPError as e:
            logger.error(f"HTTP error {e.response.status_code}: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            return None

    def get_first_translation(self) -> str | None:
        """
        Отдельный метод для извлечения перевода (опционально)
        """
        data = self.lookup()
        try:
            return data['def'][0]['tr'][0]['text']
        except (KeyError, IndexError, TypeError):
            return None
