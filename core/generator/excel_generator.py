import os
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Font
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
    _fill_return_request(wb, data)
    _fill_section2(wb, data)
    _fill_appendix5(wb, data)

    wb.save(excel_path)
    return excel_path


def _safe_write(ws, cell_ref, value, font_size=None):
    value = str(value) if value is not None else ""
    cell = ws[cell_ref]
    if isinstance(cell, MergedCell):
        for merged_range in ws.merged_cells.ranges:
            if cell.coordinate in merged_range:
                parent_cell = ws.cell(row=merged_range.min_row, column=merged_range.min_col)
                parent_cell.value = value
                if font_size:
                    parent_cell.font = Font(size=font_size)
                return
    else:
        cell.value = value
        if font_size:
            cell.font = Font(size=font_size)


def _write_fio_field(ws, text, start_col, row):
    text = str(text) if text else ""
    col = start_col
    for char in text:
        if col > 60:
            break
        col_letter = get_column_letter(col)
        _safe_write(ws, f"{col_letter}{row}", char.upper())
        col += 2


def _write_number_field(ws, text, start_col, row):
    text = str(text) if text else ""
    col = start_col
    for char in text:
        col_letter = get_column_letter(col)
        _safe_write(ws, f"{col_letter}{row}", char)
        col += 1


# ==================== ТИТУЛЬНЫЙ ЛИСТ ====================

def _fill_title(wb, data):
    ws = wb["Титульный лист"]

    _write_inn(ws, data.get("taxpayer_inn", ""))

    _safe_write(ws, "K11", "0")
    _safe_write(ws, "M11", "0")
    _safe_write(ws, "O11", "0")

    _safe_write(ws, "AC11", "3")
    _safe_write(ws, "AE11", "4")

    year = str(data.get("year", ""))
    if len(year) >= 4:
        _safe_write(ws, "AU11", year[0])
        _safe_write(ws, "AW11", year[1])
        _safe_write(ws, "AY11", year[2])
        _safe_write(ws, "BA11", year[3])

    tax_office = str(data.get("tax_office", ""))
    if len(tax_office) >= 4:
        _safe_write(ws, "BU11", tax_office[0])
        _safe_write(ws, "BW11", tax_office[1])
        _safe_write(ws, "BY11", tax_office[2])
        _safe_write(ws, "CA11", tax_office[3])

    _safe_write(ws, "K16", "6")
    _safe_write(ws, "M16", "4")
    _safe_write(ws, "O16", "3")

    _safe_write(ws, "AU16", "7")
    _safe_write(ws, "AW16", "6")
    _safe_write(ws, "AY16", "0")

    _write_fio_field(ws, data.get("last_name", ""), 11, 18)
    _write_fio_field(ws, data.get("first_name", ""), 11, 20)
    _write_fio_field(ws, data.get("middle_name", ""), 11, 22)

    birth_date = str(data.get("birth_date", ""))
    if len(birth_date) == 10:
        _safe_write(ws, "K31", birth_date[0])
        _safe_write(ws, "M31", birth_date[1])
        _safe_write(ws, "Q31", birth_date[3])
        _safe_write(ws, "S31", birth_date[4])
        _safe_write(ws, "W31", birth_date[6])
        _safe_write(ws, "Y31", birth_date[7])
        _safe_write(ws, "AA31", birth_date[8])
        _safe_write(ws, "AC31", birth_date[9])

    _safe_write(ws, "Q33", "2")
    _safe_write(ws, "S33", "1")

    passport = str(data.get("passport", ""))
    if len(passport) == 10:
        col = 17
        for digit in passport:
            col_letter = get_column_letter(col)
            _safe_write(ws, f"{col_letter}35", digit)
            col += 2

    _safe_write(ws, "Y37", "1")

    _write_fio_field(ws, data.get("taxpayer_phone", ""), 21, 39)

    _safe_write(ws, "S44", "0")
    _safe_write(ws, "U44", "0")
    _safe_write(ws, "W44", "5")

    _safe_write(ws, "BQ44", "0")
    _safe_write(ws, "BS44", "0")
    _safe_write(ws, "BU44", "0")

    _safe_write(ws, "D48", "1")

    _write_fio_field(ws, data.get("last_name", ""), 2, 50)
    _write_fio_field(ws, data.get("first_name", ""), 2, 52)
    _write_fio_field(ws, data.get("middle_name", ""), 2, 54)

    today = datetime.now().strftime("%d%m%Y")
    _safe_write(ws, "V56", today[0])
    _safe_write(ws, "X56", today[1])
    _safe_write(ws, "AB56", today[2])
    _safe_write(ws, "AD56", today[3])
    _safe_write(ws, "AH56", today[4])
    _safe_write(ws, "AJ56", today[5])
    _safe_write(ws, "AL56", today[6])
    _safe_write(ws, "AN56", today[7])


def _write_inn(ws, inn):
    inn = str(inn) if inn else ""
    if len(inn) < 12:
        return
    cols = [25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45, 47]
    for i, digit in enumerate(inn[:12]):
        col_letter = get_column_letter(cols[i])
        _safe_write(ws, f"{col_letter}1", digit)


# ==================== РАЗДЕЛ 1 ====================

def _fill_section1(wb, data):
    ws = wb["Раздел 1"]

    _safe_write(ws, "X4", "002")

    last_name = str(data.get("last_name", ""))
    _safe_write(ws, "E7", last_name.upper())

    first_name = str(data.get("first_name", ""))
    if first_name:
        _safe_write(ws, "AH7", first_name[0].upper())

    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _safe_write(ws, "AK7", middle_name[0].upper())

    kbk = "18210102010011000110"
    _write_number_field(ws, kbk, 21, 12)

    tax_return = data.get("tax_return", 0)
    tax_return_str = str(round(tax_return))
    _write_number_field(ws, tax_return_str, 21, 18)

    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V63", today, font_size=8)


# ==================== ПРИЛОЖЕНИЕ К РАЗДЕЛУ 1 ====================

def _fill_return_request(wb, data):
    ws = wb["Прил-е к Разделу 1"]

    # Фамилия
    last_name = str(data.get("last_name", ""))
    _safe_write(ws, "E7", last_name.upper())

    # И.
    first_name = str(data.get("first_name", ""))
    if first_name:
        _safe_write(ws, "AH7", first_name[0].upper())

    # О.
    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _safe_write(ws, "AK7", middle_name[0].upper())

    # Сумма к возврату (010): M11-Y11
    tax_return = data.get("tax_return", 0)
    tax_return_str = str(round(tax_return))
    _write_number_field(ws, tax_return_str, 13, 11)  # M = 13

    # БИК (020): U15-AC15 (9 цифр)
    bik = str(data.get("bik", ""))
    if len(bik) == 9:
        _write_number_field(ws, bik, 21, 15)  # U = 21

    # Номер счёта (030): U17-AN17 (20 цифр)
    account = str(data.get("account", ""))
    if len(account) == 20:
        _write_number_field(ws, account, 21, 17)

    # Номер карты (040): U19-AN19
    card = str(data.get("card", ""))
    if card:
        _write_number_field(ws, card, 21, 19)

    # Дата: V50
    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V50", today, font_size=8)


# ==================== РАЗДЕЛ 2 ====================

def _fill_section2(wb, data):
    ws = wb["Раздел 2"]
    _safe_write(ws, "D1", "1")
    deduction = data.get("deduction_amount", 0)
    _safe_write(ws, "D40", f"{deduction:,.2f}")
    tax_return = data.get("tax_return", 0)
    _safe_write(ws, "D160", str(round(tax_return)))


# ==================== ПРИЛОЖЕНИЕ 5 ====================

def _fill_appendix5(wb, data):
    ws = wb["Прил.5"]
    deduction_type = data.get("deduction_type", "")
    deduction = data.get("deduction_amount", 0)

    if deduction_type == "medical":
        _safe_write(ws, "D140", f"{deduction:,.2f}")
    elif deduction_type == "education":
        _safe_write(ws, "D130", f"{deduction:,.2f}")

    _safe_write(ws, "D180", f"{deduction:,.2f}")
    _safe_write(ws, "D190", f"{deduction:,.2f}")