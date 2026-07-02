import re
import openpyxl
from bot.config import MEDICAL_KEYWORDS, EDUCATION_KEYWORDS


async def parse_excel(file_path: str) -> list[dict]:
    """
    Парсит Excel банковской выписки.
    Ожидаемые колонки: Дата операции, Валюта, Сумма, Вид платежа (Зачисление/Списание), Описание.

    Возвращает список платежей:
    [
        {
            "date": "22.05.2026",
            "amount": 8000.00,
            "description": "Оплата товаров/услуг в ГБУЗ СО ТГКБ №5",
            "category": "medical"
        },
        ...
    ]
    """
    wb = openpyxl.load_workbook(file_path, data_only=True)
    ws = wb.active

    # Определяем, где заканчиваются заголовки и начинаются данные
    data_start_row = _find_data_start(ws)

    payments = []

    for row in ws.iter_rows(min_row=data_start_row, values_only=True):
        if not row or all(cell is None for cell in row):
            continue

        # Собираем строку в текст для анализа
        row_text = " ".join(str(cell) for cell in row if cell is not None)

        # Извлекаем дату
        date = _extract_date(row)
        if not date:
            continue

        # Извлекаем сумму (ищем расход — отрицательную или со словом "Списание")
        amount = _extract_amount(row)
        if amount is None or amount >= 0:
            continue  # пропускаем зачисления и нули

        # Извлекаем описание
        description = _extract_description_from_row(row)

        # Определяем категорию
        category = _detect_category(description)
        if category:
            payments.append({
                "date": date,
                "amount": abs(amount),
                "description": description,
                "category": category
            })

    wb.close()
    return payments


def _find_data_start(ws) -> int:
    """
    Ищет строку, с которой начинаются данные.
    Пропускает заголовки с реквизитами счёта, шапку таблицы.
    Ищем первую строку, где есть дата в формате ДД.ММ.ГГГГ.
    """
    for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
        for cell in row:
            if cell and re.search(r"\d{2}\.\d{2}\.\d{4}", str(cell)):
                return row_idx
    return 1


def _extract_date(row) -> str | None:
    """
    Ищет дату в строке Excel.
    Поддерживает форматы: ДД.ММ.ГГГГ, datetime объект.
    """
    import datetime as dt

    for cell in row:
        if cell is None:
            continue

        # Если ячейка — объект datetime
        if isinstance(cell, (dt.date, dt.datetime)):
            return cell.strftime("%d.%m.%Y")

        # Если строка с датой
        cell_str = str(cell)
        match = re.search(r"(\d{2}\.\d{2}\.\d{4})", cell_str)
        if match:
            return match.group(1)

    return None


def _extract_amount(row) -> float | None:
    """
    Извлекает сумму расхода из строки.
    Ищет отрицательное число или положительное с пометкой "Списание".
    """
    # Проверяем, есть ли в строке признак списания
    row_text = " ".join(str(cell) for cell in row if cell is not None)
    is_expense = "списан" in row_text.lower()

    for cell in row:
        if cell is None:
            continue

        # Если число
        if isinstance(cell, (int, float)):
            if cell < 0:
                return float(cell)
            if cell > 0 and is_expense:
                return -float(cell)

        # Если строка с суммой
        if isinstance(cell, str):
            # Ищем сумму с минусом
            match = re.search(r"-\s*(\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)", cell)
            if match:
                raw = match.group(1).replace(" ", "").replace(",", ".")
                return -float(raw)

            # Ищем сумму с ₽ и проверяем контекст на списание
            match = re.search(r"(\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)\s*₽", cell)
            if match and is_expense:
                raw = match.group(1).replace(" ", "").replace(",", ".")
                return -float(raw)

    return None


def _extract_description_from_row(row) -> str:
    """
    Собирает описание из строк Excel.
    Описание — самая длинная текстовая ячейка или всё, что не дата/сумма/валюта.
    """
    candidates = []
    for cell in row:
        if cell is None:
            continue
        cell_str = str(cell).strip()

        # Пропускаем даты
        if re.match(r"^\d{2}\.\d{2}\.\d{4}", cell_str):
            continue
        # Пропускаем время
        if re.match(r"^\d{2}:\d{2}", cell_str):
            continue
        # Пропускаем чистые числа (суммы, номера документов)
        if re.match(r"^[+-]?\d+[.,]?\d*$", cell_str.replace(" ", "")):
            continue
        # Пропускаем валюту
        if cell_str.lower() in ("₽", "rub", "rur", "руб"):
            continue
        # Пропускаем "Зачисление"/"Списание"
        if cell_str.lower() in ("зачисление", "списание", "зачисл", "списан"):
            continue

        if len(cell_str) > 3:
            candidates.append(cell_str)

    # Возвращаем самую длинную строку как описание
    if candidates:
        return max(candidates, key=len)

    # Если ничего не нашли, собираем всё вместе
    return " ".join(candidates)


def _detect_category(description: str) -> str | None:
    """
    Определяет категорию платежа по ключевым словам.
    """
    desc_lower = description.lower()

    for kw in MEDICAL_KEYWORDS:
        if kw.lower() in desc_lower:
            return "medical"

    for kw in EDUCATION_KEYWORDS:
        if kw.lower() in desc_lower:
            return "education"

    # Доп. паттерны для медицины
    medical_patterns = [
        r"гбуз", r"г\s*б\s*у\s*з", r"поликлин", r"госпитал",
        r"диспансер", r"роддом", r"мед\s*центр", r"стоматолог", r"зубн",
        r"тгкб", r"гкб", r"црб", r"ркб", r"клиник"
    ]
    for pattern in medical_patterns:
        if re.search(pattern, desc_lower):
            return "medical"

    # Доп. паттерны для образования
    education_patterns = [
        r"универ", r"институт", r"академи", r"колледж",
        r"школ", r"гимназ", r"лицей", r"вуз", r"образован"
    ]
    for pattern in education_patterns:
        if re.search(pattern, desc_lower):
            return "education"

    return None