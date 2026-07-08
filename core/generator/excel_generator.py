import os
import shutil
from openpyxl import load_workbook
from bot.config import DATA_TEMP_DIR

# Абсолютный путь к шаблону относительно этого файла
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(_BASE_DIR, "..", "..", "templates", "ndfl_2025.xlsx")
TEMPLATE_PATH = os.path.abspath(TEMPLATE_PATH)


async def generate_excel(declaration_id: int, data: dict) -> str:
    """Заполняет шаблон 3-НДФЛ данными пользователя."""
    excel_path = os.path.join(DATA_TEMP_DIR, f"declaration_{declaration_id}.xlsx")
    shutil.copy(TEMPLATE_PATH, excel_path)

    wb = load_workbook(excel_path)

    _fill_title(wb, data)
    _fill_section1(wb, data)
    _fill_section2(wb, data)
    _fill_appendix5(wb, data)
    _fill_return_request(wb, data)

    wb.save(excel_path)
    return excel_path


def _fill_title(wb, data):
    ws = wb["Титульный лист"]
    ws["B10"] = "0"
    ws["N10"] = "34"
    ws["X10"] = data.get("year", "")
    ws["B14"] = "643"
    ws["P14"] = "760"
    ws["V24"] = "1"
    ws["B26"] = data.get("taxpayer_phone", "")
    ws["B37"] = "1"


def _fill_section1(wb, data):
    ws = wb["Раздел 1"]
    _fill_inn_on_sheet(ws, data.get("taxpayer_inn", ""))
    _set_cell_value(ws, "020", "18210102010011000110")
    tax_return = data.get("tax_return", 0)
    _set_cell_value(ws, "050", str(round(tax_return)))


def _fill_section2(wb, data):
    ws = wb["Раздел 2"]
    _fill_inn_on_sheet(ws, data.get("taxpayer_inn", ""))
    _set_cell_value(ws, "001", "1")
    deduction = data.get("deduction_amount", 0)
    _set_cell_value(ws, "040", f"{deduction:,.2f}")
    tax_return = data.get("tax_return", 0)
    _set_cell_value(ws, "160", str(round(tax_return)))


def _fill_appendix5(wb, data):
    ws = wb["Прил.5"]
    _fill_inn_on_sheet(ws, data.get("taxpayer_inn", ""))
    deduction_type = data.get("deduction_type", "")
    deduction = data.get("deduction_amount", 0)

    if deduction_type == "medical":
        _set_cell_value(ws, "140", f"{deduction:,.2f}")
    elif deduction_type == "education":
        _set_cell_value(ws, "130", f"{deduction:,.2f}")

    _set_cell_value(ws, "180", f"{deduction:,.2f}")
    _set_cell_value(ws, "190", f"{deduction:,.2f}")


def _fill_return_request(wb, data):
    ws = wb["Прил-е к Разделу 1"]
    _fill_inn_on_sheet(ws, data.get("taxpayer_inn", ""))
    tax_return = data.get("tax_return", 0)
    _set_cell_value(ws, "010", str(round(tax_return)))


def _fill_inn_on_sheet(ws, inn):
    if not inn:
        return
    for i, digit in enumerate(inn[:12]):
        col_idx = 10 + (i % 4)
        row = 1 + (i // 4)
        col_letter = chr(64 + col_idx) if col_idx <= 26 else "A" + chr(64 + col_idx - 26)
        try:
            ws[f"{col_letter}{row}"] = digit
        except Exception:
            pass


def _set_cell_value(ws, row_num, value):
    row_num = int(row_num)
    for col in ["D", "E", "F", "G"]:
        cell = ws[f"{col}{row_num}"]
        if cell.value is not None or col == "D":
            cell.value = value
            break