import os
import shutil
from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from bot.config import DATA_TEMP_DIR

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(_BASE_DIR, "..", "..", "templates", "ndfl_2025.xlsx")
TEMPLATE_PATH = os.path.abspath(TEMPLATE_PATH)


async def generate_excel(declaration_id: int, data: dict) -> str:
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


def _safe_write(ws, cell_ref, value):
    """Пишет в ячейку, даже если она MergedCell — находит родительскую."""
    cell = ws[cell_ref]
    if isinstance(cell, MergedCell):
        # Ищем объединённый диапазон, в который входит ячейка
        for merged_range in ws.merged_cells.ranges:
            if cell.coordinate in merged_range:
                parent_cell = ws[merged_range.min_row][merged_range.min_col - 1]
                parent_cell.value = value
                return
    else:
        cell.value = value


def _fill_title(wb, data):
    ws = wb["Титульный лист"]
    _safe_write(ws, "B10", "0")
    _safe_write(ws, "N10", "34")
    _safe_write(ws, "X10", data.get("year", ""))
    _safe_write(ws, "B14", "643")
    _safe_write(ws, "P14", "760")
    _safe_write(ws, "V24", "1")
    _safe_write(ws, "B26", data.get("taxpayer_phone", ""))
    _safe_write(ws, "B37", "1")


def _fill_section1(wb, data):
    ws = wb["Раздел 1"]
    _fill_inn_on_sheet(ws, data.get("taxpayer_inn", ""))
    _safe_write(ws, "D20", "18210102010011000110")
    tax_return = data.get("tax_return", 0)
    _safe_write(ws, "D50", str(round(tax_return)))


def _fill_section2(wb, data):
    ws = wb["Раздел 2"]
    _fill_inn_on_sheet(ws, data.get("taxpayer_inn", ""))
    _safe_write(ws, "D1", "1")
    deduction = data.get("deduction_amount", 0)
    _safe_write(ws, "D40", f"{deduction:,.2f}")
    tax_return = data.get("tax_return", 0)
    _safe_write(ws, "D160", str(round(tax_return)))


def _fill_appendix5(wb, data):
    ws = wb["Прил.5"]
    _fill_inn_on_sheet(ws, data.get("taxpayer_inn", ""))
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
    _fill_inn_on_sheet(ws, data.get("taxpayer_inn", ""))
    tax_return = data.get("tax_return", 0)
    _safe_write(ws, "D10", str(round(tax_return)))


def _fill_inn_on_sheet(ws, inn):
    if not inn:
        return
    for i, digit in enumerate(inn[:12]):
        col_idx = 10 + (i % 4)
        row = 1 + (i // 4)
        col_letter = chr(64 + col_idx) if col_idx <= 26 else "A" + chr(64 + col_idx - 26)
        try:
            _safe_write(ws, f"{col_letter}{row}", digit)
        except Exception:
            pass