# session_manager.py
from datetime import datetime, timedelta
from src.database import Database
import logging

logger = logging.getLogger(__name__)
db = Database()

def save_session_data(user_id, context):
    session_start = context.user_data.get('session_start')
    if not session_start:
        logger.error("Время начала сессии не найдено!")
        return

    session_end = datetime.now()
    duration = round((session_end - session_start).total_seconds() / 60, 1)
    session_end_with_buffer = session_end + timedelta(seconds=1)

    learned_words = db.count_new_learned_words(user_id, session_start, session_end_with_buffer)
    db.update_session_stats(
        user_id=user_id,
        learned_words=learned_words,
        session_duration=duration
    )
    logger.info(f"[DEBUG] Сессия сохранена: learned_words={learned_words}, duration={duration}")
