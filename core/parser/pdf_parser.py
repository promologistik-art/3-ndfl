import re
import fitz
from bot.config import MEDICAL_KEYWORDS, EDUCATION_KEYWORDS


async def parse_pdf(file_path: str) -> list[dict]:
    """
    Парсит PDF банковской выписки.
    Работает с текстовыми PDF, где данные могут быть разорваны по строкам.

    Возвращает список платежей:
    [
        {
            "date": "22.05.2026",
            "amount": 8000.00,
            "description": "Оплата товаров/услуг в ГБУЗ СО ТГКБ №5 через СБП",
            "category": "medical"
        },
        ...
    ]
    """
    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    # Объединяем разорванные строки
    lines = full_text.split("\n")
    merged_lines = _merge_broken_lines(lines)

    # Собираем блоки операций
    operations = _extract_operations(merged_lines)

    # Фильтруем только расходы с медицинскими/образовательными категориями
    payments = []
    for op in operations:
        category = _detect_category(op["description"])
        if category and op["amount"] < 0:  # только расходы
            payments.append({
                "date": op["date"],
                "amount": abs(op["amount"]),
                "description": op["description"],
                "category": category
            })

    return payments


def _merge_broken_lines(lines: list[str]) -> list[str]:
    """
    Объединяет строки, разорванные при копировании из PDF.
    Если строка не начинается с даты и не пустая — это продолжение предыдущей.
    """
    merged = []
    current = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Новая операция начинается с даты ДД.ММ.ГГГГ
        if re.match(r"^\d{2}\.\d{2}\.\d{4}\s", line):
            if current:
                merged.append(current)
            current = line
        else:
            # Продолжение предыдущей строки
            if current:
                current += " " + line

    if current:
        merged.append(current)

    return merged


def _extract_operations(lines: list[str]) -> list[dict]:
    """
    Извлекает операции из объединённых строк.
    Возвращает список словарей с date, amount, description.
    """
    operations = []

    for line in lines:
        # Извлекаем дату (первая в строке)
        date_match = re.match(r"(\d{2}\.\d{2}\.\d{4})", line)
        if not date_match:
            continue
        date = date_match.group(1)

        # Извлекаем все суммы с ₽
        amount_matches = re.findall(r"([+-]?\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)\s*₽", line)
        if not amount_matches:
            continue

        # Берём последнюю сумму (сумма в валюте счёта)
        raw_amount = amount_matches[-1].replace(" ", "").replace(",", ".")
        try:
            amount = float(raw_amount)
        except ValueError:
            continue

        # Извлекаем описание
        # Описание обычно после сумм и до следующей даты
        description = _extract_description(line)

        if description:
            operations.append({
                "date": date,
                "amount": amount,
                "description": description
            })

    return operations


def _extract_description(line: str) -> str:
    """
    Вытаскивает описание операции из строки.
    Ищет текст после сумм и знака ₽.
    """
    # Убираем дату в начале
    line_no_date = re.sub(r"^\d{2}\.\d{2}\.\d{4}\s+", "", line)

    # Убираем время если есть
    line_no_date = re.sub(r"\d{2}:\d{2}\s+", "", line_no_date)

    # Ищем позицию последнего ₽
    rub_positions = [m.end() for m in re.finditer(r"₽", line_no_date)]
    if not rub_positions:
        return ""

    # Описание начинается после последнего ₽
    desc_start = rub_positions[-1]
    description = line_no_date[desc_start:].strip()

    # Чистим от остатков номеров документов (чисел в начале)
    description = re.sub(r"^\d+\s*", "", description)

    # Убираем номер карты если есть (последнее длинное число)
    description = re.sub(r"\s*\d{10,}\s*$", "", description)

    return description.strip()


def _detect_category(description: str) -> str | None:
    """
    Определяет категорию платежа по ключевым словам в описании.
    Возвращает 'medical', 'education' или None.
    """
    desc_lower = description.lower()

    # Проверяем медицинские ключевые слова
    for kw in MEDICAL_KEYWORDS:
        if kw.lower() in desc_lower:
            return "medical"

    # Проверяем образовательные ключевые слова
    for kw in EDUCATION_KEYWORDS:
        if kw.lower() in desc_lower:
            return "education"

    # Дополнительные паттерны для мед. учреждений
    medical_patterns = [
        r"гбуз",           # государственное бюджетное учреждение здравоохранения
        r"г\s*б\s*у\s*з",  # то же с пробелами
        r"поликлин",
        r"госпитал",
        r"диспансер",
        r"роддом",
        r"мед\s*центр",
        r"стоматолог",
        r"зубн",
    ]
    for pattern in medical_patterns:
        if re.search(pattern, desc_lower):
            return "medical"

    # Дополнительные паттерны для образования
    education_patterns = [
        r"универ",
        r"институт",
        r"академи",
        r"колледж",
        r"школ",
        r"гимназ",
        r"лицей",
        r"вуз",
        r"образован",
    ]
    for pattern in education_patterns:
        if re.search(pattern, desc_lower):
            return "education"

    return None