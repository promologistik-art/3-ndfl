import re
import os
import openpyxl
from bot.config import MEDICAL_KEYWORDS, EDUCATION_KEYWORDS, DATA_TEMP_DIR


async def parse_excel(file_path: str) -> list[dict]:
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    # Отладка в файл
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
        debug_lines.append(f"Строка: {' | '.join(cells[:4])}")

        date = _extract_date(cells)
        if not date:
            debug_lines.append("  -> дата не найдена")
            continue

        amount = _extract_amount(cells)
        if amount is None:
            debug_lines.append(f"  -> сумма не найдена, дата: {date}")
            continue

        description = _extract_description(cells)
        if not description:
            debug_lines.append(f"  -> описание не найдено, дата: {date}, сумма: {amount}")
            continue

        category = _detect_category(description)

        debug_lines.append(f"  -> OK: {date} | {amount} | {description[:80]} | {category}")

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
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        for cell in row:
            if cell and "дата операции" in str(cell).lower():
                return row_idx + 1
    return None


def _extract_date(cells: list[str]) -> str | None:
    for c in cells:
        match = re.search(r"(\d{2}\.\d{2}\.\d{4})", c)
        if match:
            return match.group(1)
    return None


def _extract_amount(cells: list[str]) -> float | None:
    for c in cells:
        match = re.search(r"([+-])\s*(\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)\s*₽", c)
        if match:
            sign = match.group(1)
            raw = match.group(2).replace(" ", "").replace(",", ".")
            try:
                amount = float(raw)
                return -amount if sign == "-" else amount
            except ValueError:
                pass
    return None


def _extract_description(cells: list[str]) -> str:
    description = ""
    for c in cells:
        if re.search(r"\d{2}\.\d{2}\.\d{4}", c):
            continue
        if "₽" in c:
            continue
        if re.match(r"^\d+$", c):
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