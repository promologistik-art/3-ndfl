import os
import uuid
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from core.models import User, Declaration, get_session
from bot.config import DATA_TEMP_DIR, DEMO_LIMIT, MONTHLY_LIMIT, ACCESS_DEMO, ACCESS_MONTHLY, ACCESS_UNLIMITED, ADMIN_IDS
from bot.keyboards.user import deduction_type_kb, confirm_manual_input_kb, confirm_data_kb, download_kb
from core.parser.pdf_parser import parse_pdf
from core.calculator.social import calculate_social_deduction
from core.generator.excel_generator import generate_excel

router = Router()


class UploadStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_photo = State()
    waiting_for_manual_name = State()
    waiting_for_manual_inn = State()
    waiting_for_manual_amount = State()
    waiting_for_taxpayer_inn = State()
    waiting_for_last_name = State()
    waiting_for_first_name = State()
    waiting_for_middle_name = State()
    waiting_for_birth_date = State()
    waiting_for_passport = State()
    waiting_for_tax_office = State()
    waiting_for_taxpayer_phone = State()


@router.callback_query(F.data == "menu_upload")
async def start_upload(callback: CallbackQuery, state: FSMContext, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return

    if user.access_type == ACCESS_DEMO and user.declarations_used >= DEMO_LIMIT:
        await callback.answer("Лимит демо-доступа исчерпан (1 декларация)", show_alert=True)
        return
    if user.access_type == ACCESS_MONTHLY and user.declarations_used >= MONTHLY_LIMIT:
        await callback.answer("Лимит на этот месяц исчерпан", show_alert=True)
        return

    await callback.message.edit_text(
        "📤 Отправьте банковскую выписку в формате PDF или Excel.\n\n"
        "Я проанализирую её и найду платежи, подходящие для налогового вычета.",
        reply_markup=None
    )
    await state.set_state(UploadStates.waiting_for_file)
    await callback.answer()


@router.message(UploadStates.waiting_for_file, F.document)
async def handle_file(message: Message, state: FSMContext, user: User = None):
    if not user:
        await message.answer("Ошибка. Попробуйте позже.")
        return

    document = message.document
    file_name = document.file_name.lower()

    if not (file_name.endswith(".pdf") or file_name.endswith(".xlsx") or file_name.endswith(".xls")):
        await message.answer("❌ Поддерживаются только PDF и Excel файлы. Отправьте файл ещё раз.")
        return

    os.makedirs(DATA_TEMP_DIR, exist_ok=True)
    file_id = document.file_id
    file = await message.bot.get_file(file_id)
    file_ext = file_name.split(".")[-1]
    temp_path = os.path.join(DATA_TEMP_DIR, f"{uuid.uuid4()}.{file_ext}")
    await message.bot.download_file(file.file_path, temp_path)

    await message.answer("🔍 Анализирую выписку...")

    try:
        if file_ext == "pdf":
            parsed_payments = await parse_pdf(temp_path)
        else:
            from core.parser.excel_parser import parse_excel
            parsed_payments = await parse_excel(temp_path)
    except Exception as e:
        await message.answer(f"❌ Ошибка при обработке файла: {e}")
        os.remove(temp_path)
        await state.clear()
        return

    os.remove(temp_path)

    if not parsed_payments:
        await message.answer(
            "❌ Не обнаружено платежей, подходящих для налогового вычета.\n\n"
            "Убедитесь, что в выписке есть операции по медицинским или образовательным услугам."
        )
        await state.clear()
        return

    medical = [p for p in parsed_payments if p["category"] == "medical"]
    education = [p for p in parsed_payments if p["category"] == "education"]

    response = "✅ Найдены подходящие платежи:\n\n"
    if medical:
        total_med = sum(p["amount"] for p in medical)
        response += f"🏥 Медицинские услуги: {len(medical)} платежа(ей) на сумму <b>{total_med:,.2f} ₽</b>\n"
    if education:
        total_edu = sum(p["amount"] for p in education)
        response += f"🎓 Обучение: {len(education)} платежа(ей) на сумму <b>{total_edu:,.2f} ₽</b>\n"

    response += "\nВыберите тип вычета для расчёта:"

    await state.update_data(parsed_payments=parsed_payments)
    await message.answer(response, reply_markup=deduction_type_kb())
    await state.clear()


@router.message(UploadStates.waiting_for_file)
async def handle_wrong_format(message: Message):
    await message.answer("❌ Отправьте файл в формате PDF или Excel.")


@router.callback_query(F.data.startswith("deduction_"))
async def handle_deduction_choice(callback: CallbackQuery, state: FSMContext, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return

    deduction_type = callback.data.replace("deduction_", "")
    if deduction_type not in ("medical", "education"):
        await callback.answer("Этот тип вычета пока в разработке", show_alert=True)
        return

    await callback.message.answer(
        f"Для расчёта {_deduction_name(deduction_type)} нужны данные об учреждении.\n\n"
        f"Вы можете загрузить фото договора/справки или ввести данные вручную.",
        reply_markup=confirm_manual_input_kb()
    )
    await state.update_data(deduction_type=deduction_type)
    await state.set_state(UploadStates.waiting_for_photo)
    await callback.answer()


@router.callback_query(F.data == "upload_photo", UploadStates.waiting_for_photo)
async def request_photo(callback: CallbackQuery):
    await callback.message.edit_text(
        "📸 Отправьте фото договора или справки об оплате.\n\n"
        "Я распознаю наименование учреждения и ИНН."
    )
    await callback.answer()


@router.message(UploadStates.waiting_for_photo, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    await message.answer("🔍 Распознаю документ...")

    os.makedirs(DATA_TEMP_DIR, exist_ok=True)
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    temp_path = os.path.join(DATA_TEMP_DIR, f"{uuid.uuid4()}.jpg")
    await message.bot.download_file(file.file_path, temp_path)

    try:
        from core.parser.ocr import ocr_document
        result = await ocr_document(temp_path)
    except Exception:
        await message.answer("❌ Не удалось распознать документ. Введите данные вручную.")
        os.remove(temp_path)
        await state.set_state(UploadStates.waiting_for_manual_name)
        await message.answer("Введите наименование учреждения:")
        return

    os.remove(temp_path)

    if not result or not result.get("name") or not result.get("inn"):
        await message.answer("⚠️ Не удалось извлечь все данные. Введите вручную.")
        await state.set_state(UploadStates.waiting_for_manual_name)
        await message.answer("Введите наименование учреждения:")
        return

    data = await state.get_data()
    payments = data.get("parsed_payments", [])
    deduction_type = data.get("deduction_type", "medical")
    category_payments = [p for p in payments if p["category"] == deduction_type]
    total_sum = sum(p["amount"] for p in category_payments)

    await state.update_data(
        institution_name=result.get("name"),
        institution_inn=result.get("inn"),
        total_amount=total_sum
    )

    await message.answer(
        f"📋 Проверьте распознанные данные:\n\n"
        f"🏢 Учреждение: <b>{result.get('name')}</b>\n"
        f"🔢 ИНН: <b>{result.get('inn')}</b>\n"
        f"💰 Сумма: <b>{total_sum:,.2f} ₽</b>\n\n"
        f"Всё верно?",
        reply_markup=confirm_data_kb()
    )


@router.callback_query(F.data == "manual_input", UploadStates.waiting_for_photo)
async def start_manual_input(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Введите наименование учреждения:")
    await state.set_state(UploadStates.waiting_for_manual_name)
    await callback.answer()


@router.message(UploadStates.waiting_for_manual_name)
async def manual_name(message: Message, state: FSMContext):
    await state.update_data(institution_name=message.text)
    await message.answer("Введите ИНН учреждения:")
    await state.set_state(UploadStates.waiting_for_manual_inn)


@router.message(UploadStates.waiting_for_manual_inn)
async def manual_inn(message: Message, state: FSMContext):
    await state.update_data(institution_inn=message.text)

    data = await state.get_data()
    payments = data.get("parsed_payments", [])
    deduction_type = data.get("deduction_type", "medical")
    category_payments = [p for p in payments if p["category"] == deduction_type]
    total_sum = sum(p["amount"] for p in category_payments)

    await message.answer(
        f"💰 Общая сумма платежей по категории: <b>{total_sum:,.2f} ₽</b>\n\n"
        f"Введите сумму расходов (можно изменить):"
    )
    await state.update_data(total_amount=total_sum)
    await state.set_state(UploadStates.waiting_for_manual_amount)


@router.message(UploadStates.waiting_for_manual_amount)
async def manual_amount(message: Message, state: FSMContext):
    try:
        amount = float(message.text.replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Введите число.")
        return

    data = await state.get_data()
    await state.update_data(total_amount=amount)

    await message.answer(
        f"📋 Проверьте введённые данные:\n\n"
        f"🏢 Учреждение: <b>{data.get('institution_name')}</b>\n"
        f"🔢 ИНН: <b>{data.get('institution_inn')}</b>\n"
        f"💰 Сумма: <b>{amount:,.2f} ₽</b>\n\n"
        f"Всё верно?",
        reply_markup=confirm_data_kb()
    )


@router.callback_query(F.data == "confirm_yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return

    await callback.message.answer(
        "📝 Для заполнения декларации нужны ваши данные.\n\n"
        "Введите ваш ИНН (12 цифр):"
    )
    await state.set_state(UploadStates.waiting_for_taxpayer_inn)
    await callback.answer()


@router.message(UploadStates.waiting_for_taxpayer_inn)
async def taxpayer_inn(message: Message, state: FSMContext):
    inn = message.text.strip()
    if not inn.isdigit() or len(inn) != 12:
        await message.answer("❌ ИНН должен содержать 12 цифр. Попробуйте ещё раз:")
        return

    await state.update_data(taxpayer_inn=inn)
    await message.answer("Введите вашу фамилию:")
    await state.set_state(UploadStates.waiting_for_last_name)


@router.message(UploadStates.waiting_for_last_name)
async def last_name(message: Message, state: FSMContext):
    await state.update_data(last_name=message.text.strip().upper())
    await message.answer("Введите ваше имя:")
    await state.set_state(UploadStates.waiting_for_first_name)


@router.message(UploadStates.waiting_for_first_name)
async def first_name(message: Message, state: FSMContext):
    await state.update_data(first_name=message.text.strip().upper())
    await message.answer("Введите ваше отчество (если нет — поставьте прочерк):")
    await state.set_state(UploadStates.waiting_for_middle_name)


@router.message(UploadStates.waiting_for_middle_name)
async def middle_name(message: Message, state: FSMContext):
    await state.update_data(middle_name=message.text.strip().upper())
    await message.answer("Введите дату рождения в формате ДД.ММ.ГГГГ:")
    await state.set_state(UploadStates.waiting_for_birth_date)


@router.message(UploadStates.waiting_for_birth_date)
async def birth_date(message: Message, state: FSMContext):
    import re
    text = message.text.strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", text):
        await message.answer("❌ Неверный формат. Введите дату как ДД.ММ.ГГГГ:")
        return
    await state.update_data(birth_date=text)
    await message.answer("Введите серию и номер паспорта (4 цифры серии и 6 цифр номера, слитно):\nНапример: 4510123456")
    await state.set_state(UploadStates.waiting_for_passport)


@router.message(UploadStates.waiting_for_passport)
async def passport(message: Message, state: FSMContext):
    text = message.text.strip().replace(" ", "")
    if not text.isdigit() or len(text) != 10:
        await message.answer("❌ Должно быть 10 цифр. Введите серию и номер слитно:")
        return
    await state.update_data(passport=text)
    await message.answer("Введите код налогового органа (4 цифры):")
    await state.set_state(UploadStates.waiting_for_tax_office)


@router.message(UploadStates.waiting_for_tax_office)
async def tax_office(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or len(text) != 4:
        await message.answer("❌ Код налогового органа — 4 цифры. Попробуйте ещё раз:")
        return
    await state.update_data(tax_office=text)
    await message.answer("📱 Введите ваш номер телефона (в любом формате):")
    await state.set_state(UploadStates.waiting_for_taxpayer_phone)


@router.message(UploadStates.waiting_for_taxpayer_phone)
async def taxpayer_phone(message: Message, state: FSMContext, user: User = None):
    phone = message.text.strip()
    await state.update_data(taxpayer_phone=phone)

    data = await state.get_data()
    deduction_type = data.get("deduction_type", "medical")
    institution_name = data.get("institution_name", "")
    institution_inn = data.get("institution_inn", "")
    total_amount = data.get("total_amount", 0)

    calculated = calculate_social_deduction(
        deduction_type=deduction_type,
        amount=total_amount,
        institution_name=institution_name,
        institution_inn=institution_inn
    )

    await message.answer(
        f"📊 Результат расчёта:\n\n"
        f"🏢 Учреждение: <b>{institution_name}</b>\n"
        f"💰 Сумма расходов: <b>{total_amount:,.2f} ₽</b>\n"
        f"📉 Сумма вычета: <b>{calculated['deduction_amount']:,.2f} ₽</b>\n"
        f"💵 НДФЛ к возврату: <b>{calculated['tax_return']:,.2f} ₽</b>\n"
        f"📆 Год: <b>{calculated['year']}</b>"
    )

    session = next(get_session())
    try:
        declaration = Declaration(
            user_id=user.id,
            deduction_type=deduction_type,
            year=calculated["year"],
            status="calculated",
            raw_data=data.get("parsed_payments"),
            calculated_data=calculated
        )
        session.add(declaration)
        session.commit()
        session.refresh(declaration)
        declaration_id = declaration.id
    finally:
        session.close()

    if user.access_type == ACCESS_DEMO and user.telegram_id not in ADMIN_IDS:
        user.declarations_used += 1
        session2 = next(get_session())
        try:
            session2.merge(user)
            session2.commit()
        finally:
            session2.close()

        await message.answer(
            "⚠️ У вас демо-доступ. Скачивание декларации недоступно.\n"
            "Для получения полного доступа свяжитесь с администратором: <b>@silverzen</b>"
        )
    else:
        pdf_data = {
            **calculated,
            "taxpayer_inn": data.get("taxpayer_inn", ""),
            "last_name": data.get("last_name", ""),
            "first_name": data.get("first_name", ""),
            "middle_name": data.get("middle_name", ""),
            "birth_date": data.get("birth_date", ""),
            "passport": data.get("passport", ""),
            "tax_office": data.get("tax_office", ""),
            "taxpayer_phone": data.get("taxpayer_phone", ""),
        }
        excel_path = await generate_excel(declaration_id, pdf_data)

        session3 = next(get_session())
        try:
            decl = session3.get(Declaration, declaration_id)
            decl.pdf_path = excel_path
            decl.status = "generated"
            session3.commit()
        finally:
            session3.close()

        await message.answer(
            "✅ Декларация готова!",
            reply_markup=download_kb(declaration_id)
        )

        user.declarations_used += 1
        session4 = next(get_session())
        try:
            session4.merge(user)
            session4.commit()
        finally:
            session4.close()

    await state.clear()


@router.callback_query(F.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Давайте введём данные заново.")
    await state.set_state(UploadStates.waiting_for_manual_name)
    await callback.message.answer("Введите наименование учреждения:")
    await callback.answer()


@router.callback_query(F.data.startswith("download_"))
async def download_file(callback: CallbackQuery, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return

    if user.access_type == ACCESS_DEMO and user.telegram_id not in ADMIN_IDS:
        await callback.answer("Скачивание недоступно в демо-режиме", show_alert=True)
        return

    _, file_type, decl_id = callback.data.split("_", 2)
    decl_id = int(decl_id)

    session = next(get_session())
    try:
        declaration = session.get(Declaration, decl_id)
        if not declaration:
            await callback.answer("Декларация не найдена")
            return

        file_path = declaration.pdf_path
        if not file_path or not os.path.exists(file_path):
            await callback.answer("Файл не найден")
            return

        await callback.message.answer_document(FSInputFile(file_path))
    finally:
        session.close()

    await callback.answer()


def _deduction_name(deduction_type: str) -> str:
    match deduction_type:
        case "medical":
            return "медицинских услуг"
        case "education":
            return "обучения"
        case "investment":
            return "инвестиционного вычета"
        case "property":
            return "имущественного вычета"
        case _:
            return "вычета"