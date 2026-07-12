import os
import re
import zipfile
import shutil
from datetime import datetime
from xml.etree import ElementTree as ET
from bot.config import DATA_TEMP_DIR

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(_BASE_DIR, "..", "..", "templates", "ndfl_2025.xlsx")
TEMPLATE_PATH = os.path.abspath(TEMPLATE_PATH)

BASE_SHEETS = ["Титульный лист", "Раздел 1", "Прил-е к Разделу 1", "Раздел 2"]

NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
ET.register_namespace("", NS)


async def generate_excel(declaration_id: int, data: dict) -> str:
    last_name = data.get("last_name", "Декларация")
    selected = data.get("selected_deductions", {})
    today = datetime.now().strftime("%d%m%y")
    types = []
    if selected.get("medical"): types.append("мед")
    if selected.get("education"): types.append("обуч")
    if selected.get("property"): types.append("имущ")
    if selected.get("investment"): types.append("инв")
    type_str = "-".join(types) if types else "вычет"
    file_name = f"3НДФЛ_{last_name}_{today}_{type_str}.xlsx"
    excel_path = os.path.join(DATA_TEMP_DIR, file_name)

    shutil.copy(TEMPLATE_PATH, excel_path)

    print_sheets = list(BASE_SHEETS)
    if selected.get("education"): print_sheets.append("Прил.5")
    if selected.get("medical"): print_sheets.append("Прил.5 (продолжение)")
    if selected.get("property"): print_sheets.append("Прил.7")
    if selected.get("investment"):
        print_sheets.append("Прил.5")
        print_sheets.append("Расчет к прил.5")

    sheet_map = _get_sheet_map(excel_path)

    for sheet_name in print_sheets:
        if sheet_name in sheet_map:
            _fill_sheet_xml(excel_path, sheet_map[sheet_name], sheet_name, data, selected)

    _set_active_sheet(excel_path, sheet_map.get("Титульный лист", ""))

    return excel_path


def _get_sheet_map(filepath: str) -> dict:
    sheet_map = {}
    with zipfile.ZipFile(filepath, "r") as z:
        wb_xml = z.read("xl/workbook.xml").decode("utf-8")
        names = {}
        for sheet_el in re.finditer(r'<sheet[^>]*/>', wb_xml):
            name_match = re.search(r'name="([^"]*)"', sheet_el.group())
            rid_match = re.search(r'r:id="([^"]*)"', sheet_el.group())
            if name_match and rid_match:
                names[rid_match.group(1)] = name_match.group(1)

        rels_xml = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")
        for rel in re.finditer(r'<Relationship[^>]*/>', rels_xml):
            rid = re.search(r'Id="([^"]*)"', rel.group())
            target = re.search(r'Target="([^"]*)"', rel.group())
            if rid and target:
                rid_val = rid.group(1)
                if rid_val in names:
                    sheet_map[names[rid_val]] = "xl/" + target.group(1)
    return sheet_map


def _fill_sheet_xml(filepath: str, sheet_path: str, sheet_name: str, data: dict, selected: dict):
    with zipfile.ZipFile(filepath, "r") as z:
        xml_content = z.read(sheet_path).decode("utf-8")

    # Убираем BOM если есть
    if xml_content.startswith("\ufeff"):
        xml_content = xml_content[1:]

    root = ET.fromstring(xml_content)

    # Собираем строки
    rows = {}
    for row in root.findall(f"{{{NS}}}row"):
        row_num = row.get("r")
        if row_num:
            rows[int(row_num)] = row

    if sheet_name == "Титульный лист":
        _fill_title_xml(rows, root, data)
    elif sheet_name == "Раздел 1":
        _fill_section1_xml(rows, root, data)
    elif sheet_name == "Прил-е к Разделу 1":
        _fill_return_request_xml(rows, root, data)
    elif sheet_name == "Раздел 2":
        _fill_section2_xml(rows, root, data)
    elif sheet_name == "Прил.5" and selected.get("education"):
        _fill_appendix5_education_xml(rows, root, data)
    elif sheet_name == "Прил.5" and selected.get("investment"):
        _fill_appendix5_investment_xml(rows, root, data)
    elif sheet_name == "Прил.5 (продолжение)" and selected.get("medical"):
        _fill_appendix5_medical_xml(rows, root, data)
    elif sheet_name == "Прил.7":
        _fill_appendix7_xml(rows, root, data)

    new_xml = ET.tostring(root, encoding="unicode")
    _replace_in_zip(filepath, sheet_path, new_xml)


def _replace_in_zip(filepath: str, internal_path: str, content: str):
    tmp_path = filepath + ".tmp"
    with zipfile.ZipFile(filepath, "r") as zin:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == internal_path:
                    zout.writestr(item, content.encode("utf-8"))
                else:
                    zout.writestr(item, zin.read(item.filename))
    os.replace(tmp_path, filepath)


def _set_active_sheet(filepath: str, sheet_path: str):
    if not sheet_path:
        return
    # Определяем rId листа
    sheet_rid = None
    with zipfile.ZipFile(filepath, "r") as z:
        wb_xml = z.read("xl/workbook.xml").decode("utf-8")
        rels_xml = z.read("xl/_rels/workbook.xml.rels").decode("utf-8")

    # Находим rId для sheet_path
    for rel in re.finditer(r'<Relationship[^>]*/>', rels_xml):
        target = re.search(r'Target="([^"]*)"', rel.group())
        rid = re.search(r'Id="([^"]*)"', rel.group())
        if target and rid and ("xl/" + target.group(1)) == sheet_path:
            sheet_rid = rid.group(1)
            break

    if sheet_rid:
        # Добавляем activeTab в workbook.xml
        sheet_index = 0
        for i, sheet_el in enumerate(re.finditer(r'<sheet[^>]*/>', wb_xml)):
            rid_match = re.search(r'r:id="([^"]*)"', sheet_el.group())
            if rid_match and rid_match.group(1) == sheet_rid:
                sheet_index = i
                break

        # Вставляем activeTab перед </workbook>
        wb_xml = wb_xml.replace("</workbook>", f"<workbookView activeTab=\"{sheet_index}\"/></workbook>")
        _replace_in_zip_str(filepath, "xl/workbook.xml", wb_xml)


def _replace_in_zip_str(filepath: str, internal_path: str, content: str):
    tmp_path = filepath + ".tmp"
    with zipfile.ZipFile(filepath, "r") as zin:
        with zipfile.ZipFile(tmp_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                if item.filename == internal_path:
                    zout.writestr(item, content.encode("utf-8"))
                else:
                    zout.writestr(item, zin.read(item.filename))
    os.replace(tmp_path, filepath)


def _set_cell(rows: dict, root, row_num: int, col_letter: str, value: str):
    value = str(value) if value is not None else ""
    col_idx = _col_to_index(col_letter)

    # Ищем или создаём строку
    if row_num not in rows:
        row = ET.SubElement(root, f"{{{NS}}}row")
        row.set("r", str(row_num))
        rows[row_num] = row
    row = rows[row_num]

    # Ищем ячейку
    for cell in row.findall(f"{{{NS}}}c"):
        ref = cell.get("r")
        if ref and _cell_to_row_col(ref) == (row_num, col_idx):
            # Удаляем старое значение
            for child in list(cell):
                if child.tag in (f"{{{NS}}}v", f"{{{NS}}}is"):
                    cell.remove(child)
            # Устанавливаем тип inlineStr и значение
            cell.set("t", "inlineStr")
            inline_str = ET.SubElement(cell, f"{{{NS}}}is")
            t = ET.SubElement(inline_str, f"{{{NS}}}t")
            t.text = value
            return

    # Создаём новую ячейку
    cell = ET.SubElement(row, f"{{{NS}}}c")
    cell.set("r", f"{col_letter}{row_num}")
    cell.set("t", "inlineStr")
    inline_str = ET.SubElement(cell, f"{{{NS}}}is")
    t = ET.SubElement(inline_str, f"{{{NS}}}t")
    t.text = value


def _col_to_index(col: str) -> int:
    result = 0
    for char in col.upper():
        result = result * 26 + (ord(char) - ord("A") + 1)
    return result


def _cell_to_row_col(ref: str) -> tuple:
    match = re.match(r"([A-Z]+)(\d+)", ref)
    if match:
        return int(match.group(2)), _col_to_index(match.group(1))
    return 0, 0


def _index_to_col(idx: int) -> str:
    result = ""
    while idx > 0:
        idx, remainder = divmod(idx - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _write_fio_xml(rows, root, text, start_col, row):
    text = str(text) if text else ""
    col = start_col
    for char in text:
        if col > 60:
            break
        _set_cell(rows, root, row, _index_to_col(col), char.upper())
        col += 2


def _write_number_xml(rows, root, text, start_col, row):
    text = str(text) if text else ""
    col = start_col
    for char in text:
        _set_cell(rows, root, row, _index_to_col(col), char)
        col += 1


def _write_amount_xml(rows, root, amount, start_col, row):
    amount_str = f"{amount:.2f}"
    parts = amount_str.split(".")
    _write_number_xml(rows, root, parts[0], start_col, row)
    _set_cell(rows, root, row, "AM", parts[1][0])
    _set_cell(rows, root, row, "AN", parts[1][1])


# ==================== ТИТУЛЬНЫЙ ЛИСТ ====================

def _fill_title_xml(rows, root, data):
    inn = data.get("taxpayer_inn", "")
    if len(inn) >= 12:
        cols = ["Y", "AA", "AC", "AE", "AG", "AI", "AK", "AM", "AO", "AQ", "AS", "AU"]
        for i, digit in enumerate(inn[:12]):
            _set_cell(rows, root, 1, cols[i], digit)

    _set_cell(rows, root, 11, "K", "0")
    _set_cell(rows, root, 11, "M", "0")
    _set_cell(rows, root, 11, "O", "0")
    _set_cell(rows, root, 11, "AC", "3")
    _set_cell(rows, root, 11, "AE", "4")
    year = str(data.get("year", ""))
    if len(year) >= 4:
        _set_cell(rows, root, 11, "AU", year[0])
        _set_cell(rows, root, 11, "AW", year[1])
        _set_cell(rows, root, 11, "AY", year[2])
        _set_cell(rows, root, 11, "BA", year[3])

    tax_office = str(data.get("tax_office", ""))
    if len(tax_office) >= 4:
        _set_cell(rows, root, 11, "BU", tax_office[0])
        _set_cell(rows, root, 11, "BW", tax_office[1])
        _set_cell(rows, root, 11, "BY", tax_office[2])
        _set_cell(rows, root, 11, "CA", tax_office[3])

    _set_cell(rows, root, 16, "K", "6")
    _set_cell(rows, root, 16, "M", "4")
    _set_cell(rows, root, 16, "O", "3")
    _set_cell(rows, root, 16, "AU", "7")
    _set_cell(rows, root, 16, "AW", "6")
    _set_cell(rows, root, 16, "AY", "0")

    _write_fio_xml(rows, root, data.get("last_name", ""), 11, 18)
    _write_fio_xml(rows, root, data.get("first_name", ""), 11, 20)
    _write_fio_xml(rows, root, data.get("middle_name", ""), 11, 22)

    birth_date = str(data.get("birth_date", ""))
    if len(birth_date) == 10:
        _set_cell(rows, root, 31, "K", birth_date[0])
        _set_cell(rows, root, 31, "M", birth_date[1])
        _set_cell(rows, root, 31, "Q", birth_date[3])
        _set_cell(rows, root, 31, "S", birth_date[4])
        _set_cell(rows, root, 31, "W", birth_date[6])
        _set_cell(rows, root, 31, "Y", birth_date[7])
        _set_cell(rows, root, 31, "AA", birth_date[8])
        _set_cell(rows, root, 31, "AC", birth_date[9])

    _set_cell(rows, root, 33, "Q", "2")
    _set_cell(rows, root, 33, "S", "1")

    passport = str(data.get("passport", ""))
    if len(passport) == 10:
        col = 17
        for digit in passport:
            _set_cell(rows, root, 35, _index_to_col(col), digit)
            col += 2

    _set_cell(rows, root, 37, "Y", "1")

    _write_fio_xml(rows, root, data.get("taxpayer_phone", ""), 21, 39)

    total_pages = 5
    selected = data.get("selected_deductions", {})
    if selected.get("education"): total_pages += 1
    if selected.get("medical"): total_pages += 1
    if selected.get("property"): total_pages += 1
    if selected.get("investment"): total_pages += 2
    pages_str = str(total_pages).zfill(3)
    _set_cell(rows, root, 44, "S", pages_str[0])
    _set_cell(rows, root, 44, "U", pages_str[1])
    _set_cell(rows, root, 44, "W", pages_str[2])

    _set_cell(rows, root, 44, "BQ", "?")
    _set_cell(rows, root, 44, "BS", "?")
    _set_cell(rows, root, 44, "BU", "?")

    _set_cell(rows, root, 48, "D", "1")

    _write_fio_xml(rows, root, data.get("last_name", ""), 2, 50)
    _write_fio_xml(rows, root, data.get("first_name", ""), 2, 52)
    _write_fio_xml(rows, root, data.get("middle_name", ""), 2, 54)

    today = datetime.now().strftime("%d%m%Y")
    _set_cell(rows, root, 56, "V", today[0])
    _set_cell(rows, root, 56, "X", today[1])
    _set_cell(rows, root, 56, "AB", today[2])
    _set_cell(rows, root, 56, "AD", today[3])
    _set_cell(rows, root, 56, "AH", today[4])
    _set_cell(rows, root, 56, "AJ", today[5])
    _set_cell(rows, root, 56, "AL", today[6])
    _set_cell(rows, root, 56, "AN", today[7])


# ==================== РАЗДЕЛ 1 ====================

def _fill_section1_xml(rows, root, data):
    _set_cell(rows, root, 7, "E", data.get("last_name", "").upper())
    first_name = str(data.get("first_name", ""))
    if first_name:
        _set_cell(rows, root, 7, "AH", first_name[0].upper())
    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _set_cell(rows, root, 7, "AK", middle_name[0].upper())

    _write_number_xml(rows, root, "18210102010011000110", 21, 12)

    tax_to_pay = data.get("tax_to_pay", 0)
    tax_return = data.get("tax_return", 0)
    if tax_to_pay > 0:
        _write_number_xml(rows, root, str(round(tax_to_pay)), 21, 16)
    elif tax_return > 0:
        _write_number_xml(rows, root, str(round(tax_return)), 21, 18)

    today = datetime.now().strftime("%d.%m.%Y")
    _set_cell(rows, root, 63, "V", today)


# ==================== ПРИЛОЖЕНИЕ К РАЗДЕЛУ 1 ====================

def _fill_return_request_xml(rows, root, data):
    _set_cell(rows, root, 7, "E", data.get("last_name", "").upper())
    first_name = str(data.get("first_name", ""))
    if first_name:
        _set_cell(rows, root, 7, "AH", first_name[0].upper())
    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _set_cell(rows, root, 7, "AK", middle_name[0].upper())

    tax_return = data.get("tax_return", 0)
    _write_number_xml(rows, root, str(round(tax_return)), 13, 11)
    bik = str(data.get("bik", ""))
    if len(bik) == 9:
        _write_number_xml(rows, root, bik, 21, 15)
    account = str(data.get("account", ""))
    if len(account) == 20:
        _write_number_xml(rows, root, account, 21, 17)
    card = str(data.get("card", ""))
    if card:
        _write_number_xml(rows, root, card, 21, 19)
    today = datetime.now().strftime("%d.%m.%Y")
    _set_cell(rows, root, 50, "V", today)


# ==================== РАЗДЕЛ 2 ====================

def _fill_section2_xml(rows, root, data):
    _set_cell(rows, root, 7, "E", data.get("last_name", "").upper())
    first_name = str(data.get("first_name", ""))
    if first_name:
        _set_cell(rows, root, 7, "AH", first_name[0].upper())
    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _set_cell(rows, root, 7, "AK", middle_name[0].upper())

    _set_cell(rows, root, 9, "Y", "0")
    _set_cell(rows, root, 9, "Z", "1")
    income = data.get("income", 0)
    _write_amount_xml(rows, root, income, 25, 11)
    deduction = data.get("total_deduction", 0)
    _write_amount_xml(rows, root, deduction, 25, 17)
    tax_base = max(0, income - deduction)
    _write_amount_xml(rows, root, tax_base, 25, 21)
    tax_calculated = round(tax_base * 0.13)
    _write_number_xml(rows, root, str(tax_calculated), 25, 24)
    tax_paid = data.get("tax_paid", 0)
    _write_number_xml(rows, root, str(round(tax_paid)), 25, 26)
    tax_to_pay = data.get("tax_to_pay", 0)
    tax_return = data.get("tax_return", 0)
    if tax_to_pay > 0:
        _write_number_xml(rows, root, str(round(tax_to_pay)), 25, 38)
    if tax_return > 0:
        _write_number_xml(rows, root, str(round(tax_return)), 25, 40)
    today = datetime.now().strftime("%d.%m.%Y")
    _set_cell(rows, root, 59, "V", today)


# ==================== ПРИЛОЖЕНИЕ 5 ====================

def _fill_appendix5_education_xml(rows, root, data):
    _set_cell(rows, root, 7, "E", data.get("last_name", "").upper())
    first_name = str(data.get("first_name", ""))
    if first_name:
        _set_cell(rows, root, 7, "AH", first_name[0].upper())
    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _set_cell(rows, root, 7, "AK", middle_name[0].upper())

    education_total = data.get("education_total", 0)
    _write_amount_xml(rows, root, education_total, 26, 42)
    today = datetime.now().strftime("%d.%m.%Y")
    _set_cell(rows, root, 47, "V", today)


def _fill_appendix5_medical_xml(rows, root, data):
    _set_cell(rows, root, 7, "E", data.get("last_name", "").upper())
    first_name = str(data.get("first_name", ""))
    if first_name:
        _set_cell(rows, root, 7, "AH", first_name[0].upper())
    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _set_cell(rows, root, 7, "AK", middle_name[0].upper())

    medical_total = data.get("medical_total", 0)
    _write_amount_xml(rows, root, medical_total, 26, 9)
    _write_amount_xml(rows, root, medical_total, 26, 23)
    _write_amount_xml(rows, root, medical_total, 26, 29)
    _write_amount_xml(rows, root, medical_total, 26, 31)
    today = datetime.now().strftime("%d.%m.%Y")
    _set_cell(rows, root, 54, "V", today)


def _fill_appendix5_investment_xml(rows, root, data):
    _set_cell(rows, root, 7, "E", data.get("last_name", "").upper())
    first_name = str(data.get("first_name", ""))
    if first_name:
        _set_cell(rows, root, 7, "AH", first_name[0].upper())
    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _set_cell(rows, root, 7, "AK", middle_name[0].upper())

    investment_amount = data.get("investment_amount", 0)
    _write_amount_xml(rows, root, investment_amount, 26, 42)
    today = datetime.now().strftime("%d.%m.%Y")
    _set_cell(rows, root, 47, "V", today)


# ==================== ПРИЛОЖЕНИЕ 7 ====================

def _fill_appendix7_xml(rows, root, data):
    _set_cell(rows, root, 7, "E", data.get("last_name", "").upper())
    first_name = str(data.get("first_name", ""))
    if first_name:
        _set_cell(rows, root, 7, "AH", first_name[0].upper())
    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _set_cell(rows, root, 7, "AK", middle_name[0].upper())

    property_price = data.get("property_price", data.get("property_total", 0))
    property_mortgage = data.get("property_mortgage", 0)
    property_object_type = data.get("property_object_type", "5")
    property_cadastral = data.get("property_cadastral", "")
    property_address = data.get("property_address", "")
    property_act_date = data.get("property_act_date", "")
    property_reg_date = data.get("property_reg_date", "")
    income = data.get("income", 0)
    total_deduction = data.get("total_deduction", 0)

    _set_cell(rows, root, 10, "K", property_object_type)
    _set_cell(rows, root, 10, "Y", "0")
    _set_cell(rows, root, 10, "Z", "1")
    _set_cell(rows, root, 12, "Y", "2")

    if property_cadastral:
        _write_number_xml(rows, root, property_cadastral, 1, 14)

    if property_address:
        lines = [property_address[i:i+40] for i in range(0, len(property_address), 40)]
        for idx, line in enumerate(lines[:7]):
            row = 16 + idx * 2
            for col_idx, char in enumerate(line):
                if col_idx >= 40:
                    break
                _set_cell(rows, root, row, _index_to_col(col_idx + 1), char)

    if property_act_date and len(property_act_date) == 10:
        _set_cell(rows, root, 30, "AD", property_act_date[0])
        _set_cell(rows, root, 30, "AE", property_act_date[1])
        _set_cell(rows, root, 30, "AG", property_act_date[3])
        _set_cell(rows, root, 30, "AH", property_act_date[4])
        _set_cell(rows, root, 30, "AJ", property_act_date[6])
        _set_cell(rows, root, 30, "AK", property_act_date[7])
        _set_cell(rows, root, 30, "AL", property_act_date[8])
        _set_cell(rows, root, 30, "AM", property_act_date[9])

    if property_reg_date and len(property_reg_date) == 10:
        _set_cell(rows, root, 32, "AD", property_reg_date[0])
        _set_cell(rows, root, 32, "AE", property_reg_date[1])
        _set_cell(rows, root, 32, "AG", property_reg_date[3])
        _set_cell(rows, root, 32, "AH", property_reg_date[4])
        _set_cell(rows, root, 32, "AJ", property_reg_date[6])
        _set_cell(rows, root, 32, "AK", property_reg_date[7])
        _set_cell(rows, root, 32, "AL", property_reg_date[8])
        _set_cell(rows, root, 32, "AM", property_reg_date[9])

    ded_price = min(property_price, 2_000_000)
    _write_amount_xml(rows, root, ded_price, 30, 34)

    if property_mortgage > 0:
        ded_mortgage = min(property_mortgage, 3_000_000)
        _write_amount_xml(rows, root, ded_mortgage, 30, 36)

    tax_base = max(0, income - total_deduction)
    _write_amount_xml(rows, root, tax_base, 26, 51)
    _write_amount_xml(rows, root, ded_price, 30, 53)

    remaining = max(0, property_price - ded_price)
    _write_amount_xml(rows, root, remaining, 30, 57)

    today = datetime.now().strftime("%d.%m.%Y")
    _set_cell(rows, root, 63, "V", today)