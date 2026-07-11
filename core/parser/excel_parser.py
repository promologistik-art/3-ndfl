import re
import openpyxl
from bot.config import MEDICAL_KEYWORDS, EDUCATION_KEYWORDS


async def parse_excel(file_path: str) -> list[dict]:
    """
    Парсит Excel банковской выписки (Озон Банк и подобные).
    Структура: шапка с реквизитами, затем таблица с колонками:
    Дата операции | Документ | Назначение платежа | Сумма (рубли) | Валюта

    Возвращает список платежей:
    [
        {
            "date": "26.04.2025",
            "amount": 4000.00,
            "description": "Перевод ... через СБП. Отправитель: Алексей Станиславович Ч.",
            "category": None
        },
        ...
    ]
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    # Ищем строку с заголовком таблицы ("Дата операции")
    data_start_row = None
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        for cell in row:
            if cell and "дата операции" in str(cell).lower():
                data_start_row = row_idx + 1
                break
        if data_start_row:
            break

    if not data_start_row:
        wb.close()
        return []

    payments = []

    for row in ws.iter_rows(min_row=data_start_row, values_only=True):
        if not row or all(cell is None for cell in row):
            continue

        cells = [str(c).strip() if c is not None else "" for c in row]

        # Ищем дату в формате ДД.ММ.ГГГГ
        date = None
        for c in cells:
            match = re.search(r"(\d{2}\.\d{2}\.\d{4})", c)
            if match:
                date = match.group(1)
                break
        if not date:
            continue

        # Ищем сумму со знаком и ₽
        amount = None
        for c in cells:
            match = re.search(r"([+-])\s*(\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)\s*₽", c)
            if match:
                sign = match.group(1)
                raw = match.group(2).replace(" ", "").replace(",", ".")
                try:
                    amount = float(raw)
                    if sign == "-":
                        amount = -amount
                except ValueError:
                    pass
                break
        if amount is None:
            continue

        # Описание — самая длинная текстовая ячейка (не дата, не сумма)
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

        # Чистим описание
        description = description.replace('"', "").strip()
        description = re.sub(r"\s+", " ", description)

        if not description:
            continue

        category = _detect_category(description)

        payments.append({
            "date": date,
            "amount": abs(amount) if amount < 0 else amount,
            "description": description,
            "category": category
        })

    wb.close()
    return payments


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