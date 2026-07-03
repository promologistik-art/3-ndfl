import re
import os
import fitz
from bot.config import DATA_TEMP_DIR


# Только явные медицинские учреждения
MEDICAL_PATTERNS = [
    r"гбуз", r"г\s*б\s*у\s*з", r"тгкб", r"гкб", r"црб", r"ркб",
    r"поликлиник", r"больниц", r"госпитал", r"диспансер",
    r"стоматолог", r"роддом", r"мед\s*центр", r"клиник\s",
    r"сан\s*часть", r"мсч", r"нмиц", r"фгбу", r"фгбун",
]

# Только явные образовательные учреждения
EDUCATION_PATTERNS = [
    r"университет", r"универ\s", r"институт\s", r"академи",
    r"колледж", r"лицей", r"гимназ", r"школ\s", r"вуз\s",
    r"техникум", r"училищ",
]


async def parse_pdf(file_path: str) -> list[dict]:
    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    debug_path = os.path.join(DATA_TEMP_DIR, "parsed_text.txt")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    # Убираем колонтитулы
    full_text = _clean_footer_header(full_text)

    # Извлекаем операции
    operations = _extract_operations_from_text(full_text)

    payments = []
    for op in operations:
        category = _detect_category(op["description"])
        if category and op["amount"] < 0:
            payments.append({
                "date": op["date"],
                "amount": abs(op["amount"]),
                "description": op["description"],
                "category": category
            })

    return payments


def _clean_footer_header(text: str) -> str:
    """
    Полностью удаляет колонтитулы с реквизитами банка и лицензией.
    """
    # Удаляем строки, содержащие реквизиты банка (они повторяются на каждой странице)
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Пропускаем строки колонтитула
        if any(x in stripped for x in [
            "ООО «ВБ Банк»",
            "ИНН 0102000578",
            "ОГРН 1020100002340",
            "Большая Ордынка",
            "8 800 770-77-70",
            "www.wb-bank.ru",
            "info@wb-bank.ru",
            "Универсальная лицензия",
            "от 22 января 2026 года",
        ]):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _extract_operations_from_text(text: str) -> list[dict]:
    operations = []

    # Ищем начало таблицы
    table_start = text.find("Дата и время\nоперации")
    if table_start == -1:
        table_start = text.find("Дата и время операции")
    if table_start == -1:
        return operations

    body = text[table_start:]

    # Ищем паттерн начала операции: дата + время на следующей строке
    pattern = r"(\d{2}\.\d{2}\.\d{4})\s*\n\s*(\d{2}:\d{2})"
    matches = list(re.finditer(pattern, body))

    for i, match in enumerate(matches):
        date = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]

        # Ищем отрицательную сумму
        amount_match = re.search(r"-(\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)\s*₽", block)
        if not amount_match:
            continue

        raw_amount = amount_match.group(1).replace(" ", "").replace(",", ".")
        try:
            amount = float(raw_amount)
        except ValueError:
            continue

        # Описание: всё после последнего ₽
        rub_matches = list(re.finditer(r"₽", block))
        if not rub_matches:
            continue

        desc_start = rub_matches[-1].end()
        description = block[desc_start:]
        description = _clean_description(description)

        if description:
            operations.append({
                "date": date,
                "amount": -amount,
                "description": description
            })

    return operations


def _clean_description(text: str) -> str:
    # Убираем строки с датами и временем
    text = re.sub(r"\d{2}\.\d{2}\.\d{4}\s*\n?\s*\d{2}:\d{2}", " ", text)
    text = re.sub(r"\d{2}\.\d{2}\.\d{4}", " ", text)
    text = re.sub(r"\d{2}:\d{2}", " ", text)
    # Убираем ID транзакций
    text = re.sub(r"ID\s*[-\s]*[A-Z0-9]{10,}", " ", text)
    # Убираем длинные числа (номера карт, счетов)
    text = re.sub(r"\b\d{10,}\b", " ", text)
    # Убираем оставшиеся числа
    text = re.sub(r"\b\d+\b", " ", text)
    # Убираем тире в начале
    text = text.strip("- ")
    # Убираем лишние пробелы
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _detect_category(description: str) -> str | None:
    desc_lower = description.lower()

    for pattern in MEDICAL_PATTERNS:
        if re.search(pattern, desc_lower):
            return "medical"

    for pattern in EDUCATION_PATTERNS:
        if re.search(pattern, desc_lower):
            return "education"

    return None