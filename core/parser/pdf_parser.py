import re
import os
import fitz
from bot.config import MEDICAL_KEYWORDS, EDUCATION_KEYWORDS, PROPERTY_KEYWORDS, INVESTMENT_KEYWORDS, DATA_TEMP_DIR


async def parse_pdf(file_path: str) -> list[dict]:
    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    debug_path = os.path.join(DATA_TEMP_DIR, "parsed_text.txt")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    full_text = _clean_footer_header(full_text)
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
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if any(x in stripped for x in [
            "ООО «ВБ Банк»", "ИНН 0102000578", "ОГРН 1020100002340",
            "Большая Ордынка", "8 800 770-77-70", "www.wb-bank.ru",
            "info@wb-bank.ru", "Универсальная лицензия", "от 22 января 2026 года",
        ]):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def _extract_operations_from_text(text: str) -> list[dict]:
    operations = []

    table_start = text.find("Дата и время\nоперации")
    if table_start == -1:
        table_start = text.find("Дата и время операции")
    if table_start == -1:
        return operations

    body = text[table_start:]

    pattern = r"(\d{2}\.\d{2}\.\d{4})\s*\n\s*(\d{2}:\d{2})"
    matches = list(re.finditer(pattern, body))

    for i, match in enumerate(matches):
        date = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]

        amount_match = re.search(r"([+-])[\s]*(\d{1,3}(?:[\s,]\d{3})*(?:[.]\d{2})?)\s*₽", block)
        if not amount_match:
            continue

        sign = amount_match.group(1)
        raw_amount = amount_match.group(2).replace(" ", "").replace(",", "")
        try:
            amount = float(raw_amount)
            if sign == "-":
                amount = -amount
        except ValueError:
            continue

        rub_matches = list(re.finditer(r"₽", block))
        if not rub_matches:
            continue

        desc_start = rub_matches[-1].end()
        description = block[desc_start:]
        description = _clean_description(description)

        if description:
            operations.append({
                "date": date,
                "amount": amount,
                "description": description
            })

    return operations


def _clean_description(text: str) -> str:
    text = re.sub(r"\d{2}\.\d{2}\.\d{4}\s*\n?\s*\d{2}:\d{2}", " ", text)
    text = re.sub(r"\d{2}\.\d{2}\.\d{4}", " ", text)
    text = re.sub(r"\d{2}:\d{2}", " ", text)
    text = re.sub(r"ID\s*[-\s]*[A-Z0-9]{10,}", " ", text)
    text = re.sub(r"\b\d{10,}\b", " ", text)
    text = text.strip("- ")
    text = re.sub(r"\s+", " ", text)
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

    for kw in MEDICAL_KEYWORDS:
        if kw.lower() in desc_lower: return "medical"
    for kw in EDUCATION_KEYWORDS:
        if kw.lower() in desc_lower: return "education"
    for kw in PROPERTY_KEYWORDS:
        if kw.lower() in desc_lower: return "property"
    for kw in INVESTMENT_KEYWORDS:
        if kw.lower() in desc_lower: return "investment"

    medical_patterns = [
        r"гбуз", r"г\s*б\s*у\s*з", r"поликлин", r"госпитал", r"диспансер",
        r"роддом", r"мед\s*центр", r"стоматолог", r"зубн", r"тгкб", r"гкб",
        r"црб", r"ркб", r"клиник", r"больниц", r"медицин", r"аптек", r"лечени",
        r"диагност", r"анализ", r"хирург", r"терапевт", r"врач", r"медосмотр", r"санатор"
    ]
    for pattern in medical_patterns:
        if re.search(pattern, desc_lower): return "medical"

    education_patterns = [
        r"универ", r"институт", r"академи", r"колледж", r"школ", r"гимназ",
        r"лицей", r"вуз", r"образован", r"обучен", r"курс", r"тренинг",
        r"семинар", r"репетитор", r"автошкол", r"музыкальн", r"спортивн", r"техникум", r"училищ"
    ]
    for pattern in education_patterns:
        if re.search(pattern, desc_lower): return "education"

    property_patterns = [
        r"купл", r"продаж", r"гараж", r"квартир", r"дом", r"недвижим",
        r"ипотек", r"дду", r"долев", r"участк", r"земел", r"коттедж",
        r"таунхаус", r"апартамент", r"жил", r"строй", r"новострой"
    ]
    for pattern in property_patterns:
        if re.search(pattern, desc_lower): return "property"

    investment_patterns = [
        r"иис", r"инвестиционный счет", r"инвестиционный счёт",
        r"брокерский счет", r"брокерский счёт", r"инвест"
    ]
    for pattern in investment_patterns:
        if re.search(pattern, desc_lower): return "investment"

    return None