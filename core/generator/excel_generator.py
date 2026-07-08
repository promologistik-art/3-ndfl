import os
from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.utils import get_column_letter
from bot.config import DATA_TEMP_DIR

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(_BASE_DIR, "..", "..", "templates", "ndfl_2025.xlsx")
TEMPLATE_PATH = os.path.abspath(TEMPLATE_PATH)


async def generate_excel(declaration_id: int, data: dict) -> str:
    excel_path = os.path.join(DATA_TEMP_DIR, f"declaration_{declaration_id}.xlsx")
    wb = load_workbook(TEMPLATE_PATH)

    _fill_title(wb, data)
    _fill_section1(wb, data)
    _fill_section2(wb, data)
    _fill_appendix5(wb, data)
    _fill_return_request(wb, data)

    wb.save(excel_path)
    return excel_path


def _safe_write(ws, cell_ref, value):
    value = str(value) if value is not None else ""
    cell = ws[cell_ref]
    if isinstance(cell, MergedCell):
        for merged_range in ws.merged_cells.ranges:
            if cell.coordinate in merged_range:
                parent_cell = ws.cell(row=merged_range.min_row, column=merged_range.min_col)
                parent_cell.value = value
                return
    else:
        cell.value = value


def _write_inn(ws, inn):
    inn = str(inn) if inn else ""
    if len(inn) < 12:
        return
    cols = [25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45, 47]
    for i, digit in enumerate(inn[:12]):
        col_letter = get_column_letter(cols[i])
        _safe_write(ws, f"{col_letter}1", digit)


def _write_fio_field(ws, text, start_col, row):
    text = str(text) if text else ""
    col = start_col
    for char in text:
        if col > 60:
            break
        col_letter = get_column_letter(col)
        _safe_write(ws, f"{col_letter}{row}", char.upper())
        col += 2


def _fill_title(wb, data):
    ws = wb["Титульный лист"]

    # ИНН
    _write_inn(ws, data.get("taxpayer_inn", ""))

    # Номер корректировки
    _safe_write(ws, "K11", "0")
    _safe_write(ws, "M11", "0")
    _safe_write(ws, "O11", "0")

    # Налоговый период
    _safe_write(ws, "AC11", "3")
    _safe_write(ws, "AE11", "4")

    # Отчётный год
    year = str(data.get("year", ""))
    if len(year) >= 4:
        _safe_write(ws, "AU11", year[0])
        _safe_write(ws, "AW11", year[1])
        _safe_write(ws, "AY11", year[2])
        _safe_write(ws, "BA11", year[3])

    # Код налогового органа
    tax_office = str(data.get("tax_office", ""))
    if len(tax_office) >= 4:
        _safe_write(ws, "BU11", tax_office[0])
        _safe_write(ws, "BW11", tax_office[1])
        _safe_write(ws, "BY11", tax_office[2])
        _safe_write(ws, "CA11", tax_office[3])

    # Код страны
    _safe_write(ws, "K16", "6")
    _safe_write(ws, "M16", "4")
    _safe_write(ws, "O16", "3")

    # Код категории
    _safe_write(ws, "AU16", "7")
    _safe_write(ws, "AW16", "6")
    _safe_write(ws, "AY16", "0")

    # Фамилия
    _write_fio_field(ws, data.get("last_name", ""), 11, 18)

    # Имя
    _write_fio_field(ws, data.get("first_name", ""), 11, 20)

    # Отчество
    _write_fio_field(ws, data.get("middle_name", ""), 11, 22)

    # Дата рождения
    birth_date = str(data.get("birth_date", ""))
    if len(birth_date) == 10:
        _safe_write(ws, "K28", birth_date[0])
        _safe_write(ws, "M28", birth_date[1])
        _safe_write(ws, "O28", birth_date[3])
        _safe_write(ws, "Q28", birth_date[4])
        _safe_write(ws, "S28", birth_date[6])
        _safe_write(ws, "U28", birth_date[7])
        _safe_write(ws, "W28", birth_date[8])
        _safe_write(ws, "Y28", birth_date[9])

    # Код вида документа — паспорт РФ
    _safe_write(ws, "K30", "2")
    _safe_write(ws, "M30", "1")

    # Серия и номер паспорта
    passport = str(data.get("passport", ""))
    if len(passport) == 10:
        col = 11
        for digit in passport:
            col_letter = get_column_letter(col)
            _safe_write(ws, f"{col_letter}32", digit)
            col += 2

    # Код статуса
    _safe_write(ws, "BI28", "1")

    # Телефон
    _write_fio_field(ws, data.get("taxpayer_phone", ""), 21, 39)

    # Достоверность подтверждаю
    _safe_write(ws, "B37", "1")


def _fill_section1(wb, data):
    ws = wb["Раздел 1"]
    _write_inn(ws, data.get("taxpayer_inn", ""))
    _safe_write(ws, "D20", "18210102010011000110")
    tax_return = data.get("tax_return", 0)
    _safe_write(ws, "D50", str(round(tax_return)))


def _fill_section2(wb, data):
    ws = wb["Раздел 2"]
    _write_inn(ws, data.get("taxpayer_inn", ""))
    _safe_write(ws, "D1", "1")
    deduction = data.get("deduction_amount", 0)
    _safe_write(ws, "D40", f"{deduction:,.2f}")
    tax_return = data.get("tax_return", 0)
    _safe_write(ws, "D160", str(round(tax_return)))


def _fill_appendix5(wb, data):
    ws = wb["Прил.5"]
    _write_inn(ws, data.get("taxpayer_inn", ""))
    deduction_type = data.get("deduction_type", "")
    deduction = data.get("deduction_amount", 0)

    if deduction_type == "medical":
        _safe_write(ws, "D140", f"{deduction:,.2f}")
    elif deduction_type == "education":
        _safe_write(ws, "D130", f"{deduction:,.2f}")

    _safe_write(ws, "D180", f"{deduction:,.2f}")
    _safe_write(ws, "D190", f"{deduction:,.2f}")


def _fill_return_request(wb, data):
    ws = wb["Прил-е к Разделу 1"]
    _write_inn(ws, data.get("taxpayer_inn", ""))
    tax_return = data.get("tax_return", 0)
    _safe_write(ws, "D10", str(round(tax_return)))