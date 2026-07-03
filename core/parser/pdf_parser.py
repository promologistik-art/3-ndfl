import re
import os
import fitz
from bot.config import MEDICAL_KEYWORDS, EDUCATION_KEYWORDS, DATA_TEMP_DIR


async def parse_pdf(file_path: str) -> list[dict]:
    doc = fitz.open(file_path)
    full_text = ""
    for page in doc:
        full_text += page.get_text() + "\n"
    doc.close()

    # Отладка: записываем сырой текст в файл
    debug_path = os.path.join(DATA_TEMP_DIR, "parsed_text.txt")
    with open(debug_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    lines = full_text.split("\n")
    merged_lines = _merge_broken_lines(lines)
    operations = _extract_operations(merged_lines)

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


def _merge_broken_lines(lines: list[str]) -> list[str]:
    merged = []
    current = ""

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if re.match(r"^\d{2}\.\d{2}\.\d{4}\s", line):
            if current:
                merged.append(current)
            current = line
        else:
            if current:
                current += " " + line

    if current:
        merged.append(current)

    return merged


def _extract_operations(lines: list[str]) -> list[dict]:
    operations = []

    for line in lines:
        date_match = re.match(r"(\d{2}\.\d{2}\.\d{4})", line)
        if not date_match:
            continue
        date = date_match.group(1)

        amount_matches = re.findall(r"([+-]?\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)\s*₽", line)
        if not amount_matches:
            continue

        raw_amount = amount_matches[-1].replace(" ", "").replace(",", ".")
        try:
            amount = float(raw_amount)
        except ValueError:
            continue

        description = _extract_description(line)

        if description:
            operations.append({
                "date": date,
                "amount": amount,
                "description": description
            })

    return operations


def _extract_description(line: str) -> str:
    line_no_date = re.sub(r"^\d{2}\.\d{2}\.\d{4}\s+", "", line)
    line_no_date = re.sub(r"\d{2}:\d{2}\s+", "", line_no_date)

    rub_positions = [m.end() for m in re.finditer(r"₽", line_no_date)]
    if not rub_positions:
        return ""

    desc_start = rub_positions[-1]
    description = line_no_date[desc_start:].strip()
    description = re.sub(r"^\d+\s*", "", description)
    description = re.sub(r"\s*\d{10,}\s*$", "", description)

    return description.strip()


def _detect_category(description: str) -> str | None:
    desc_lower = description.lower()

    for kw in MEDICAL_KEYWORDS:
        if kw.lower() in desc_lower:
            return "medical"

    for kw in EDUCATION_KEYWORDS:
        if kw.lower() in desc_lower:
            return "education"

    medical_patterns = [
        r"гбуз", r"г\s*б\s*у\s*з", r"поликлин", r"госпитал",
        r"диспансер", r"роддом", r"мед\s*центр", r"стоматолог", r"зубн",
        r"тгкб", r"гкб", r"црб", r"ркб", r"клиник"
    ]
    for pattern in medical_patterns:
        if re.search(pattern, desc_lower):
            return "medical"

    education_patterns = [
        r"универ", r"институт", r"академи", r"колледж",
        r"школ", r"гимназ", r"лицей", r"вуз", r"образован"
    ]
    for pattern in education_patterns:
        if re.search(pattern, desc_lower):
            return "education"

    return None