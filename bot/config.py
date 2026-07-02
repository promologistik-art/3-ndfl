import os
from dotenv import load_dotenv

load_dotenv(override=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
DATABASE_URL = os.getenv("DATABASE_URL")

DATA_TEMP_DIR = "data/temp"

ACCESS_DEMO = "demo"
ACCESS_MONTHLY = "monthly"
ACCESS_UNLIMITED = "unlimited"

DEMO_LIMIT = 1
MONTHLY_LIMIT = 1

MEDICAL_KEYWORDS = [
    "больниц", "клиник", "поликлиник", "госпитал", "диспансер",
    "медицин", "медцентр", "мед центр", "стоматолог", "зубн",
    "аптек", "лечени", "диагност", "анализ", "хирург",
    "терапевт", "врач", "медосмотр", "протезирование", "санатор",
    "роддом", "гбуз", "тгкб", "гкб", "црб", "ркб"
]

EDUCATION_KEYWORDS = [
    "обучен", "универ", "институт", "колледж", "школ",
    "образован", "вуз", "академ", "тренинг", "семинар",
    "репетитор", "автошкол", "музыкальн", "спортивн",
    "гимназ", "лицей", "курс"
]

DEDUCTION_TYPES = {
    "medical": "Медицинские услуги",
    "education": "Обучение",
    "investment": "Инвестиционный вычет",
    "property": "Имущественный вычет"
}