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

    # Убираем колонтитулы и служебные строки между страницами
    full_text = _clean_footer_header(full_text)

    # Находим все блоки операций
    operations = _extract_operations_from_text(full_text)

    # Фильтруем по категориям
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
    Убирает повторяющиеся колонтитулы с реквизитами банка,
    которые вставляются между страницами.
    """
    # Паттерн колонтитула: начинается с "ООО «ВБ Банк»" и заканчивается номером лицензии
    footer_pattern = r"ООО «ВБ Банк»[^\n]*\n(?:[^\n]*\n)*?(?:Универсальная лицензия[^\n]*\n)"
    text = re.sub(footer_pattern, "", text)
    return text


def _extract_operations_from_text(text: str) -> list[dict]:
    """
    Извлекает операции из текста PDF.
    Ищет блоки: дата + время + ... + сумма + описание.
    """
    operations = []

    # Ищем начало таблицы — строка "Дата и время операции"
    table_start = text.find("Дата и время\nоперации")
    if table_start == -1:
        table_start = text.find("Дата и время операции")
    if table_start == -1:
        return operations

    # Берём текст после заголовка таблицы
    body = text[table_start:]

    # Ищем все позиции дат формата ДД.ММ.ГГГГ, за которыми сразу идёт время ЧЧ:ММ
    # Это паттерн начала операции: "ДД.ММ.ГГГГ\nЧЧ:ММ"
    pattern = r"(\d{2}\.\d{2}\.\d{4})\s*\n\s*(\d{2}:\d{2})"
    matches = list(re.finditer(pattern, body))

    for i, match in enumerate(matches):
        date = match.group(1)
        # Начало блока операции — сразу после времени
        start = match.end()

        # Конец блока — начало следующей операции или конец текста
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = len(body)

        block = body[start:end]

        # Ищем сумму (отрицательную) в блоке
        amount_match = re.search(r"-(\d{1,3}(?:\s?\d{3})*(?:[.,]\d{2})?)\s*₽", block)
        if not amount_match:
            continue

        raw_amount = amount_match.group(1).replace(" ", "").replace(",", ".")
        try:
            amount = float(raw_amount)
        except ValueError:
            continue

        # Описание — всё после последнего знака ₽ в блоке
        rub_matches = list(re.finditer(r"₽", block))
        if not rub_matches:
            continue

        desc_start = rub_matches[-1].end()
        description = block[desc_start:]

        # Чистим описание
        description = _clean_description(description)

        if description:
            operations.append({
                "date": date,
                "amount": -amount,
                "description": description
            })

    return operations


def _clean_description(text: str) -> str:
    """
    Очищает описание операции от мусора:
    - номера документов
    - ID транзакций
    - номера карт
    - остатки дат и времени
    """
    # Убираем даты
    text = re.sub(r"\d{2}\.\d{2}\.\d{4}", "", text)
    # Убираем время
    text = re.sub(r"\d{2}:\d{2}", "", text)
    # Убираем длинные числовые идентификаторы (номера карт, ID)
    text = re.sub(r"\b\d{10,}\b", "", text)
    # Убираем оставшиеся числа (номера документов)
    text = re.sub(r"\b\d+\b", "", text)
    # Убираем знак тире в начале
    text = text.strip("- ")
    # Схлопываем множественные пробелы и переносы строк
    text = re.sub(r"\s+", " ", text)

    return text.strip()


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