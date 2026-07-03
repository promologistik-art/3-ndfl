import re
import os
import fitz
from bot.config import DATA_TEMP_DIR


MEDICAL_PATTERNS = [
    r"гбуз", r"г\s*б\s*у\s*з", r"тгкб", r"гкб", r"црб", r"ркб",
    r"поликлиник", r"больниц", r"госпитал", r"диспансер",
    r"стоматолог", r"роддом", r"мед\s*центр", r"клиник\s",
    r"сан\s*часть", r"мсч", r"нмиц", r"фгбу", r"фгбун",
]

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

    debug_ops_path = os.path.join(DATA_TEMP_DIR, "parsed_debug.txt")
    debug_lines = []

    full_text = _clean_footer_header(full_text)
    operations = _extract_operations_from_text(full_text, debug_lines)

    with open(debug_ops_path, "w", encoding="utf-8") as f:
        f.write("\n".join(debug_lines))

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
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
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


def _extract_operations_from_text(text: str, debug_lines: list) -> list[dict]:
    operations = []

    table_start = text.find("Дата и время\nоперации")
    if table_start == -1:
        table_start = text.find("Дата и время операции")
    if table_start == -1:
        debug_lines.append("[ERROR] Не найдена шапка таблицы")
        return operations

    body = text[table_start:]

    pattern = r"(\d{2}\.\d{2}\.\d{4})\s*\n\s*(\d{2}:\d{2})"
    matches = list(re.finditer(pattern, body))

    debug_lines.append(f"[INFO] Всего дат с временем: {len(matches)}")

    for i, match in enumerate(matches):
        date = match.group(1)
        time = match.group(2)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]

        # Исправленный regex суммы: поддерживает и пробел, и запятую как разделитель тысяч
        # Примеры: "+5,000.00 ₽", "-8,000.00 ₽", "+200.00 ₽", "-1 200.00 ₽"
        amount_match = re.search(
            r"([+-])[\s]*(\d{1,3}(?:[\s,]\d{3})*(?:[.]\d{2})?)\s*₽",
            block
        )
        if not amount_match:
            debug_lines.append(f"[SKIP] {date} {time} — нет суммы с ₽")
            continue

        sign = amount_match.group(1)
        raw_amount = amount_match.group(2).replace(" ", "").replace(",", "")
        try:
            amount = float(raw_amount)
            if sign == "-":
                amount = -amount
        except ValueError:
            debug_lines.append(f"[SKIP] {date} {time} — не распарсить сумму: {raw_amount}")
            continue

        # Описание: всё после последнего ₽
        rub_matches = list(re.finditer(r"₽", block))
        if not rub_matches:
            debug_lines.append(f"[SKIP] {date} {time} — нет знака ₽")
            continue

        desc_start = rub_matches[-1].end()
        raw_description = block[desc_start:]
        description = _clean_description(raw_description)

        debug_lines.append(f"[OK] {date} {time} | сумма: {amount} | сырое: {repr(raw_description[:150])}")
        debug_lines.append(f"     очищенное: {repr(description[:150])}")
        debug_lines.append("")

        if description:
            operations.append({
                "date": date,
                "amount": amount,
                "description": description
            })

    return operations


def _clean_description(text: str) -> str:
    # Убираем строки с датами и временем
    text = re.sub(r"\d{2}\.\d{2}\.\d{4}\s*\n?\s*\d{2}:\d{2}", " ", text)
    text = re.sub(r"\d{2}\.\d{2}\.\d{4}", " ", text)
    text = re.sub(r"\d{2}:\d{2}", " ", text)
    # Убираем ID транзакций (длинные буквенно-цифровые коды)
    text = re.sub(r"ID\s*[-\s]*[A-Z0-9]{10,}", " ", text)
    # Убираем одиночные длинные числа (номера карт, счетов) — 10+ цифр подряд
    text = re.sub(r"\b\d{10,}\b", " ", text)
    # Убираем тире в начале
    text = text.strip("- ")
    # Убираем лишние пробелы
    text = re.sub(r"\s+", " ", text)
    # Убираем мусор от шапки таблицы если попал в описание
    text = re.sub(r"Дата и время операции.*", "", text)
    text = re.sub(r"Дата отражения по счету.*", "", text)
    text = re.sub(r"Номер документа.*", "", text)
    text = re.sub(r"Сумма в валюте операции.*", "", text)
    text = re.sub(r"Сумма в валюте счета.*", "", text)
    text = re.sub(r"Описание операции.*", "", text)
    text = re.sub(r"Номер карты.*", "", text)
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