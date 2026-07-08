import os
import shutil
from openpyxl import load_workbook
from bot.config import DATA_TEMP_DIR

TEMPLATE_PATH = os.path.join("templates", "ndfl_2025.xlsx")


async def generate_excel(declaration_id: int, data: dict) -> str:
    """Заполняет шаблон 3-НДФЛ данными пользователя."""
    excel_path = os.path.join(DATA_TEMP_DIR, f"declaration_{declaration_id}.xlsx")

    # Копируем шаблон
    shutil.copy(TEMPLATE_PATH, excel_path)

    wb = load_workbook(excel_path)

    # === Титульный лист ===
    _fill_title(wb, data)

    # === Раздел 1 ===
    _fill_section1(wb, data)

    # === Раздел 2 ===
    _fill_section2(wb, data)

    # === Приложение 5 ===
    _fill_appendix5(wb, data)

    # === Приложение к Разделу 1 (заявление на возврат) ===
    _fill_return_request(wb, data)

    wb.save(excel_path)
    return excel_path


def _fill_title(wb, data):
    """Титульный лист."""
    ws = wb["Титульный лист"]

    # ИНН
    inn = data.get("taxpayer_inn", "")
    for col in ["A", "B", "C", "D", "E", "F", "G"]:
        for row in range(1, 4):
            ws[f"{col}{row}"] = ""

    # Номер корректировки
    ws["B10"] = "0"
    # Налоговый период
    ws["N10"] = "34"
    # Отчётный год
    ws["X10"] = data.get("year", "")
    # Код налогового органа — оставляем пустым
    # Код страны
    ws["B14"] = "643"
    # Код категории
    ws["P14"] = "760"
    # ФИО
    ws["B17"] = ""  # Фамилия
    ws["B19"] = ""  # Имя
    ws["B21"] = ""  # Отчество
    # Статус
    ws["V24"] = "1"
    # Телефон
    ws["B26"] = data.get("taxpayer_phone", "")
    # Достоверность подтверждаю
    ws["B37"] = "1"


def _fill_section1(wb, data):
    """Раздел 1."""
    ws = wb["Раздел 1"]

    inn = data.get("taxpayer_inn", "")
    _fill_inn_on_sheet(ws, inn)

    # КБК
    _set_cell_value(ws, "020", "18210102010011000110")
    # ОКТМО — пусто
    # Сумма к возврату
    tax_return = data.get("tax_return", 0)
    _set_cell_value(ws, "050", str(round(tax_return)))


def _fill_section2(wb, data):
    """Раздел 2."""
    ws = wb["Раздел 2"]

    inn = data.get("taxpayer_inn", "")
    _fill_inn_on_sheet(ws, inn)

    # Код группы доходов
    _set_cell_value(ws, "001", "1")
    # Сумма доходов — пусто, пользователь сам
    # Сумма вычетов
    deduction = data.get("deduction_amount", 0)
    _set_cell_value(ws, "040", f"{deduction:,.2f}")
    # Сумма налога к возврату
    tax_return = data.get("tax_return", 0)
    _set_cell_value(ws, "160", str(round(tax_return)))


def _fill_appendix5(wb, data):
    """Приложение 5 — социальные вычеты."""
    ws = wb["Прил.5"]

    inn = data.get("taxpayer_inn", "")
    _fill_inn_on_sheet(ws, inn)

    deduction_type = data.get("deduction_type", "")
    amount = data.get("amount", 0)
    deduction = data.get("deduction_amount", 0)

    if deduction_type == "medical":
        # Обычное лечение — строка 140
        _set_cell_value(ws, "140", f"{deduction:,.2f}")
    elif deduction_type == "education":
        # Обучение налогоплательщика — строка 130
        _set_cell_value(ws, "130", f"{deduction:,.2f}")

    # Итого социальные вычеты — строка 180
    _set_cell_value(ws, "180", f"{deduction:,.2f}")

    # Общая сумма вычетов — строка 190
    _set_cell_value(ws, "190", f"{deduction:,.2f}")


def _fill_return_request(wb, data):
    """Приложение к Разделу 1 — заявление на возврат."""
    ws = wb["Прил-е к Разделу 1"]

    inn = data.get("taxpayer_inn", "")
    _fill_inn_on_sheet(ws, inn)

    # Сумма к возврату
    tax_return = data.get("tax_return", 0)
    _set_cell_value(ws, "010", str(round(tax_return)))
    # БИК, счёт, карта — пользователь заполнит сам


def _fill_inn_on_sheet(ws, inn):
    """Заполняет ИНН на листе (обычно колонка J, строки 1-3)."""
    if not inn:
        return
    # Пробуем стандартное расположение: J1, J2, J3 — первые 3 цифры, вторые 3, и т.д.
    # В шаблоне ФНС ИНН разбит по ячейкам
    for i, digit in enumerate(inn[:12]):
        col_idx = 10 + (i % 4)  # J, K, L, M
        row = 1 + (i // 4)      # строки 1, 2, 3
        col_letter = chr(64 + col_idx) if col_idx <= 26 else "A" + chr(64 + col_idx - 26)
        try:
            ws[f"{col_letter}{row}"] = digit
        except Exception:
            pass


def _set_cell_value(ws, row_num, value):
    """Устанавливает значение в ячейку с номером строки (адресация как в инструкции)."""
    row_num = int(row_num)
    # В шаблоне ФНС значения обычно в колонке D или E
    for col in ["D", "E", "F", "G"]:
        cell = ws[f"{col}{row_num}"]
        if cell.value is not None or col == "D":
            cell.value = value
            break