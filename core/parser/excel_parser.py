import re
import os
import openpyxl
from datetime import datetime
from bot.config import MEDICAL_KEYWORDS, EDUCATION_KEYWORDS, DATA_TEMP_DIR


async def parse_excel(file_path: str) -> list[dict]:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    debug_path = os.path.join(DATA_TEMP_DIR, "excel_debug.txt")
    debug_lines = []

    data_start_row = _find_data_start(ws)
    debug_lines.append(f"Заголовок найден: {data_start_row is not None}")

    if not data_start_row:
        _write_debug(debug_path, debug_lines)
        wb.close()
        return []

    payments = []

    for row in ws.iter_rows(min_row=data_start_row, values_only=True):
        if not row or all(cell is None for cell in row):
            continue

        cells = [str(c).strip() if c is not None else "" for c in row]

        # Дата может быть в любой ячейке, в любом формате
        date = _extract_date(cells)
        if not date:
            continue

        # Сумма может быть в любой ячейке, со знаком или без, с разными разделителями
        amount = _extract_amount(cells)
        if amount is None:
            continue

        # Описание — самая длинная текстовая ячейка
        description = _extract_description(cells)
        if not description:
            continue

        category = _detect_category(description)

        debug_lines.append(f"OK: {date} | {amount:>12.2f} | {description[:100]} | {category}")

        payments.append({
            "date": date,
            "amount": abs(amount) if amount < 0 else amount,
            "description": description,
            "category": category
        })

    debug_lines.append(f"Всего платежей: {len(payments)}")
    _write_debug(debug_path, debug_lines)

    wb.close()
    return payments


def _write_debug(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _find_data_start(ws) -> int | None:
    """Ищет строку с заголовком таблицы."""
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        row_text = " ".join(str(c).lower() for c in row if c)
        if "дата" in row_text and ("операции" in row_text or "платежа" in row_text or "проводки" in row_text):
            return row_idx + 1
    # Если заголовок не найден, ищем первую строку с датой
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        for cell in row:
            if cell and _parse_date(str(cell)):
                return row_idx
    return None


def _parse_date(text: str) -> str | None:
    """Парсит дату из строки в любом формате, возвращает ДД.ММ.ГГГГ."""
    if not text:
        return None

    text = text.strip()

    # ISO: 2025-03-18, 2025-03-18 14:24:00
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if match:
        return f"{match.group(3)}.{match.group(2)}.{match.group(1)}"

    # Российский: 18.03.2025, 18.03.2025 14:24:00
    match = re.search(r"(\d{2})\.(\d{2})\.(\d{4})", text)
    if match:
        return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"

    # Американский: 03/18/2025
    match = re.search(r"(\d{2})/(\d{2})/(\d{4})", text)
    if match:
        return f"{match.group(1)}.{match.group(2)}.{match.group(3)}"

    # С объектом datetime из Excel
    return None


def _extract_date(cells: list[str]) -> str | None:
    """Извлекает первую найденную дату из ячеек строки."""
    for c in cells:
        date = _parse_date(c)
        if date:
            return date
    return None


def _extract_amount(cells: list[str]) -> float | None:
    """Извлекает сумму из ячеек строки."""
    for c in cells:
        # С ₽: + 4 000.00 ₽, -15,000.00 ₽, 200.00 ₽
        match = re.search(r"([+-]?)\s*(\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)\s*₽", c)
        if match:
            sign = match.group(1) or "+"
            raw = match.group(2).replace(" ", "").replace(",", ".")
            try:
                amount = float(raw)
                return -amount if sign == "-" else amount
            except ValueError:
                pass

        # Без ₽: -15000, +200.00
        match = re.search(r"([+-])\s*(\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)", c)
        if match:
            raw = match.group(2).replace(" ", "").replace(",", ".")
            # Проверяем, что это именно сумма, а не номер документа
            try:
                amount = float(raw)
                if amount > 0.01:  # фильтруем нулевые суммы и номера документов
                    return -amount if match.group(1) == "-" else amount
            except ValueError:
                pass

    return None


def _extract_description(cells: list[str]) -> str:
    """Извлекает описание — самая длинная текстовая ячейка."""
    description = ""
    for c in cells:
        # Пропускаем даты
        if _parse_date(c):
            continue
        # Пропускаем суммы
        if "₽" in c:
            continue
        if re.match(r"^[+-]?\d+[.,]?\d*$", c.replace(" ", "")):
            continue
        if len(c) > len(description):
            description = c

    description = description.replace('"', "").strip()
    description = re.sub(r"\s+", " ", description)
    return description


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
        r"тгкб", r"гкб", r"црб", r"ркб", r"клиник", r"больниц",
        r"медицин", r"аптек", r"лечени", r"диагност", r"анализ",
        r"хирург", r"терапевт", r"врач", r"медосмотр", r"санатор"
    ]
    for pattern in medical_patterns:
        if re.search(pattern, desc_lower):
            return "medical"

    education_patterns = [
        r"универ", r"институт", r"академи", r"колледж",
        r"школ", r"гимназ", r"лицей", r"вуз", r"образован",
        r"обучен", r"курс", r"тренинг", r"семинар", r"репетитор",
        r"автошкол", r"музыкальн", r"спортивн", r"техникум", r"училищ"
    ]
    for pattern in education_patterns:
        if re.search(pattern, desc_lower):
            return "education"

    return None