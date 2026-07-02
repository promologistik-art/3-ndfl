async def generate_xml(declaration_id: int, data: dict) -> str:
    """
    Заглушка генерации XML для ЛК ФНС.
    Будет реализована по формату ФНС.
    Возвращает путь к файлу.
    """
    import os
    from bot.config import DATA_TEMP_DIR

    xml_path = os.path.join(DATA_TEMP_DIR, f"declaration_{declaration_id}.xml")
    
    # TODO: реализовать генерацию XML по схеме ФНС
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(f"<declaration id='{declaration_id}'>\n")
        f.write(f"  <deduction_amount>{data.get('deduction_amount', 0)}</deduction_amount>\n")
        f.write(f"  <tax_return>{data.get('tax_return', 0)}</tax_return>\n")
        f.write("</declaration>\n")

    return xml_path