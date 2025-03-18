import os
import requests
import base64
import time
import logging
import uuid
from dotenv import load_dotenv  # Для загрузки переменных окружения из .env

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SberSpeechAPI:
    def __init__(self):
        """Инициализация API с настройкой окружения и токена."""
        self.client_id = os.getenv("SBER_CLIENT_ID")
        self.client_secret = os.getenv("SBER_CLIENT_SECRET")
        self.access_token = None
        self.token_expires_at = 0  # Время истечения токена (epoch time)

        if not self.client_id or not self.client_secret:
            raise ValueError("SBER_CLIENT_ID и SBER_CLIENT_SECRET должны быть указаны в файле .env")

    def get_access_token(self):
        """Получение Access Token."""
        if self.access_token and self.token_expires_at > time.time():
            return self.access_token  # Возвращаем токен, если он ещё действителен

        url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
        credentials = f"{self.client_id}:{self.client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4())
        }
        payload = {"scope": "SALUTE_SPEECH_PERS"}

        try:
            response = requests.post(url, headers=headers, data=payload, verify=False)
            response.raise_for_status()
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            self.token_expires_at = time.time() + 1800  # Токен действует 30 минут
            logger.info("Access Token успешно получен")
            return self.access_token
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при получении токена: {e}")
            return None

    def synthesize_text(self, text, voice="female", language="ru", output_file="output.ogg"):
        """Синтезирует текст в аудио через Sber Speech API."""
        access_token = self.get_access_token()
        if not access_token:
            logger.error("Невозможно выполнить синтез речи без токена")
            return None

        url = "https://smartspeech.sber.ru/rest/v1/text:synthesize"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/text",  # Или application/ssml
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4())
        }
        payload = text  # Просто текст

        try:
            response = requests.post(url, headers=headers, data=payload, verify=False)
            response.raise_for_status()

            # Сохраняем аудиофайл
            with open(output_file, "wb") as f:
                f.write(response.content)
            logger.info(f"Аудиофайл успешно создан: {output_file}")
            return output_file
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка синтеза речи: {e}")
            return None
