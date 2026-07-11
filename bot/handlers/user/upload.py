import os
import uuid
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from core.models import User, Declaration, Profile, get_session
from bot.config import DATA_TEMP_DIR, DEMO_LIMIT, MONTHLY_LIMIT, ACCESS_DEMO, ACCESS_MONTHLY, ACCESS_UNLIMITED, ADMIN_IDS
from bot.keyboards.user import deduction_type_kb, confirm_data_kb, download_kb
from core.parser.pdf_parser import parse_pdf
from core.calculator.social import calculate_social_deduction
from core.generator.excel_generator import generate_excel
from sqlalchemy import select

router = Router()


class UploadStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_profile_choice = State()
    waiting_for_taxpayer_inn = State()
    waiting_for_fio = State()
    waiting_for_birth_date = State()
    waiting_for_passport = State()
    waiting_for_tax_office = State()
    waiting_for_taxpayer_phone = State()
    waiting_for_bik = State()
    waiting_for_account = State()
    waiting_for_card = State()
    waiting_for_income = State()
    waiting_for_tax_paid = State()
    waiting_for_confirm_calculation = State()


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

    first_date = parsed_payments[0]["date"] if parsed_payments else ""

    await state.update_data(
        parsed_payments=parsed_payments,
        medical_total=sum(p["amount"] for p in medical),
        education_total=sum(p["amount"] for p in education),
        first_payment_date=first_date,
    )
    await message.answer(response, reply_markup=deduction_type_kb())


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

    data = await state.get_data()
    if deduction_type == "medical":
        total_amount = data.get("medical_total", 0)
    else:
        total_amount = data.get("education_total", 0)

    await state.update_data(deduction_type=deduction_type, total_amount=total_amount)

    deduction_preview = min(total_amount, 150_000)
    tax_return_preview = round(deduction_preview * 0.13, 2)

    await callback.message.answer(
        f"📋 Проверьте данные для расчёта:\n\n"
        f"💰 Сумма расходов: <b>{total_amount:,.2f} ₽</b>\n"
        f"📉 Сумма вычета: <b>{deduction_preview:,.2f} ₽</b>\n"
        f"💵 НДФЛ к возврату: <b>{tax_return_preview:,.2f} ₽</b>\n\n"
        f"Всё верно?",
        reply_markup=confirm_data_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "confirm_yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return

    if user.access_type == ACCESS_DEMO and user.telegram_id not in ADMIN_IDS:
        await callback.message.answer(
            "⚠️ У вас демо-доступ. Скачивание декларации недоступно.\n"
            "Для получения полного доступа свяжитесь с администратором: <b>@silverzen</b>\n\n"
            "Расчёт будет показан в чате."
        )
        await _do_calculation_demo(callback.message, state, user)
        await callback.answer()
        return

    session = next(get_session())
    try:
        result = session.execute(
            select(Profile).where(Profile.user_id == callback.from_user.id)
        )
        profiles = result.scalars().all()
    finally:
        session.close()

    if profiles:
        text = "📝 Выберите профиль для заполнения:\n\n"
        buttons = []
        for i, p in enumerate(profiles[:5]):
            text += f"{i+1}. {p.name} (ИНН: {p.inn[:4]}...)\n"
            buttons.append([InlineKeyboardButton(
                text=f"{p.name}", callback_data=f"profile_{p.id}"
            )])
        buttons.append([InlineKeyboardButton(text="✏️ Новый профиль", callback_data="profile_new")])

        await callback.message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await state.set_state(UploadStates.waiting_for_profile_choice)
        await callback.answer()
        return

    await _start_data_input(callback.message, state)


async def _do_calculation_demo(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    deduction_type = data.get("deduction_type", "medical")
    total_amount = data.get("total_amount", 0)
    first_payment_date = data.get("first_payment_date", "")

    calculated = calculate_social_deduction(
        deduction_type=deduction_type,
        amount=total_amount,
        institution_name="",
        institution_inn="",
        payment_date=first_payment_date,
    )

    await message.answer(
        f"📊 Результат расчёта:\n\n"
        f"💰 Сумма расходов: <b>{total_amount:,.2f} ₽</b>\n"
        f"📉 Сумма вычета: <b>{calculated['deduction_amount']:,.2f} ₽</b>\n"
        f"💵 НДФЛ к возврату: <b>{calculated['tax_return']:,.2f} ₽</b>\n"
        f"📆 Год: <b>{calculated['year']}</b>\n\n"
        f"⚠️ Для скачивания декларации необходим платный доступ.\n"
        f"📩 Администратор: <b>@silverzen</b>"
    )

    user.declarations_used += 1
    session = next(get_session())
    try:
        session.merge(user)
        session.commit()
    finally:
        session.close()

    await state.clear()


async def _start_data_input(message: Message, state: FSMContext):
    await message.answer(
        "📝 Для заполнения декларации нужны ваши данные:\n\n"
        "1. ИНН (12 цифр)\n"
        "2. ФИО (Фамилия Имя Отчество)\n"
        "3. Дата рождения (ДД.ММ.ГГГГ)\n"
        "4. Серия и номер паспорта (10 цифр слитно)\n"
        "5. Код налогового органа (4 цифры)\n"
        "6. Номер телефона\n"
        "7. БИК банка (9 цифр)\n"
        "8. Номер счёта (20 цифр)\n"
        "9. Номер карты (можно пропустить)\n"
        "10. Сумма дохода из 2-НДФЛ\n"
        "11. Сумма удержанного налога из 2-НДФЛ\n\n"
        "▸ Шаг 1 из 11\n"
        "Введите ваш ИНН (12 цифр):"
    )
    await state.set_state(UploadStates.waiting_for_taxpayer_inn)


@router.callback_query(F.data.startswith("profile_"), UploadStates.waiting_for_profile_choice)
async def profile_chosen(callback: CallbackQuery, state: FSMContext, user: User = None):
    profile_id = callback.data.replace("profile_", "")

    if profile_id == "new":
        await _start_data_input(callback.message, state)
        await callback.answer()
        return

    session = next(get_session())
    try:
        p = session.get(Profile, int(profile_id))
    finally:
        session.close()

    if p:
        await state.update_data(
            taxpayer_inn=p.inn,
            last_name=p.last_name,
            first_name=p.first_name,
            middle_name=p.middle_name,
            birth_date=p.birth_date,
            passport=p.passport,
            tax_office=p.tax_office,
            taxpayer_phone=p.phone,
            bik=p.bik,
            account=p.account,
            card=p.card,
        )
        await callback.message.answer(f"✅ Загружен профиль: {p.name}.")
        await callback.message.answer(
            "▸ Шаг 10 из 11\n"
            "Введите общую сумму дохода за год из справки 2-НДФЛ (в рублях и копейках):\n\n"
            "ℹ️ Эти данные нужны для расчёта налоговой базы. "
            "Хранятся в зашифрованном виде и никому не передаются."
        )
        await state.set_state(UploadStates.waiting_for_income)

    await callback.answer()


@router.message(UploadStates.waiting_for_taxpayer_inn)
async def taxpayer_inn(message: Message, state: FSMContext):
    inn = message.text.strip()
    if not inn.isdigit() or len(inn) != 12:
        await message.answer("❌ ИНН должен содержать 12 цифр. Попробуйте ещё раз:")
        return

    await state.update_data(taxpayer_inn=inn)
    await message.answer("▸ Шаг 2 из 11\nВведите ваше ФИО полностью (Фамилия Имя Отчество):")
    await state.set_state(UploadStates.waiting_for_fio)


@router.message(UploadStates.waiting_for_fio)
async def fio(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("❌ Введите минимум фамилию и имя через пробел:")
        return

    last_name = parts[0].upper()
    first_name = parts[1].upper()
    middle_name = parts[2].upper() if len(parts) > 2 else "-"

    await state.update_data(last_name=last_name, first_name=first_name, middle_name=middle_name)
    await message.answer("▸ Шаг 3 из 11\nВведите дату рождения в формате ДД.ММ.ГГГГ:")
    await state.set_state(UploadStates.waiting_for_birth_date)


@router.message(UploadStates.waiting_for_birth_date)
async def birth_date(message: Message, state: FSMContext):
    import re
    text = message.text.strip()
    if not re.match(r"^\d{2}\.\d{2}\.\d{4}$", text):
        await message.answer("❌ Неверный формат. Введите дату как ДД.ММ.ГГГГ:")
        return
    await state.update_data(birth_date=text)
    await message.answer("▸ Шаг 4 из 11\nВведите серию и номер паспорта (10 цифр слитно):\nНапример: 4510123456")
    await state.set_state(UploadStates.waiting_for_passport)


@router.message(UploadStates.waiting_for_passport)
async def passport(message: Message, state: FSMContext):
    text = message.text.strip().replace(" ", "")
    if not text.isdigit() or len(text) != 10:
        await message.answer("❌ Должно быть 10 цифр. Введите серию и номер слитно:")
        return
    await state.update_data(passport=text)
    await message.answer(
        "▸ Шаг 5 из 11\nВведите код налогового органа (4 цифры).\n\n"
        "ℹ️ Код можно найти в личном кабинете ФНС (lkn.nalog.ru) или на сайте nalog.ru "
        "в разделе «Контакты вашей инспекции»."
    )
    await state.set_state(UploadStates.waiting_for_tax_office)


@router.message(UploadStates.waiting_for_tax_office)
async def tax_office(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or len(text) != 4:
        await message.answer("❌ Код налогового органа — 4 цифры. Попробуйте ещё раз:")
        return
    await state.update_data(tax_office=text)
    await message.answer("▸ Шаг 6 из 11\n📱 Введите ваш номер телефона (в любом формате):")
    await state.set_state(UploadStates.waiting_for_taxpayer_phone)


@router.message(UploadStates.waiting_for_taxpayer_phone)
async def taxpayer_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    await state.update_data(taxpayer_phone=phone)
    await message.answer("▸ Шаг 7 из 11\nВведите БИК банка (9 цифр):")
    await state.set_state(UploadStates.waiting_for_bik)


@router.message(UploadStates.waiting_for_bik)
async def bik(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or len(text) != 9:
        await message.answer("❌ БИК должен содержать 9 цифр. Попробуйте ещё раз:")
        return
    await state.update_data(bik=text)
    await message.answer("▸ Шаг 8 из 11\nВведите номер счёта (20 цифр):")
    await state.set_state(UploadStates.waiting_for_account)


@router.message(UploadStates.waiting_for_account)
async def account(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or len(text) != 20:
        await message.answer("❌ Номер счёта должен содержать 20 цифр. Попробуйте ещё раз:")
        return
    await state.update_data(account=text)
    await message.answer("▸ Шаг 9 из 11\nВведите номер карты (или нажмите «-» чтобы пропустить):")
    await state.set_state(UploadStates.waiting_for_card)


@router.message(UploadStates.waiting_for_card)
async def card(message: Message, state: FSMContext, user: User = None):
    text = message.text.strip()
    if text == "-":
        text = ""
    await state.update_data(card=text)

    await message.answer(
        "▸ Шаг 10 из 11\n"
        "Введите общую сумму дохода за год из справки 2-НДФЛ (в рублях и копейках):\n\n"
        "ℹ️ Эти данные нужны для расчёта налоговой базы. "
        "Хранятся в зашифрованном виде и никому не передаются."
    )
    await state.set_state(UploadStates.waiting_for_income)


@router.message(UploadStates.waiting_for_income)
async def income(message: Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Введите число.")
        return
    await state.update_data(income=amount)
    await message.answer(
        "▸ Шаг 11 из 11\n"
        "Введите сумму налога, удержанную работодателем, из справки 2-НДФЛ (в рублях):\n\n"
        "ℹ️ Хранится в зашифрованном виде и никому не передаётся."
    )
    await state.set_state(UploadStates.waiting_for_tax_paid)


@router.message(UploadStates.waiting_for_tax_paid)
async def tax_paid(message: Message, state: FSMContext, user: User = None):
    try:
        amount = float(message.text.strip().replace(",", ".").replace(" ", ""))
    except ValueError:
        await message.answer("❌ Введите число.")
        return
    await state.update_data(tax_paid=amount)

    data = await state.get_data()
    income_val = data.get("income", 0)
    deduction_val = data.get("total_amount", 0)
    tax_base = max(0, income_val - deduction_val)
    tax_calculated = round(tax_base * 0.13)
    tax_paid_val = round(amount)
    tax_to_pay = max(0, tax_calculated - tax_paid_val)
    tax_return_val = max(0, tax_paid_val - tax_calculated)

    if tax_to_pay > 0:
        await message.answer(
            f"⚠️ <b>Внимание!</b> По вашим данным получается <b>доплата {tax_to_pay:,} ₽</b>, а не возврат.\n\n"
            f"Вы указали:\n"
            f"• Доход: {income_val:,.0f} ₽\n"
            f"• Удержанный налог: {tax_paid_val:,} ₽\n"
            f"• Сумма вычета: {deduction_val:,.0f} ₽\n\n"
            f"Исчисленный налог: {tax_calculated:,} ₽\n"
            f"К доплате: {tax_to_pay:,} ₽\n\n"
            f"Возможно, данные введены неверно. Проверьте справку 2-НДФЛ.\n"
            f"Всё верно?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Да, продолжить", callback_data="calc_confirm_yes")],
                [InlineKeyboardButton(text="✏️ Исправить", callback_data="calc_confirm_no")],
            ])
        )
        await state.set_state(UploadStates.waiting_for_confirm_calculation)
        return

    await _save_profile_and_calculate(message, state, user)


@router.callback_query(F.data == "calc_confirm_yes", UploadStates.waiting_for_confirm_calculation)
async def calc_confirm_yes(callback: CallbackQuery, state: FSMContext, user: User = None):
    await _save_profile_and_calculate(callback.message, state, user)
    await callback.answer()


@router.callback_query(F.data == "calc_confirm_no", UploadStates.waiting_for_confirm_calculation)
async def calc_confirm_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Давайте исправим. Введите сумму дохода заново:")
    await state.set_state(UploadStates.waiting_for_income)
    await callback.answer()


async def _save_profile_and_calculate(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    session = next(get_session())
    try:
        profile_name = f"{data.get('last_name', '')} {data.get('first_name', '')[0]}.{data.get('middle_name', '')[0]}."
        profile = Profile(
            user_id=message.from_user.id,
            name=profile_name,
            inn=data.get("taxpayer_inn", ""),
            last_name=data.get("last_name", ""),
            first_name=data.get("first_name", ""),
            middle_name=data.get("middle_name", ""),
            birth_date=data.get("birth_date", ""),
            passport=data.get("passport", ""),
            tax_office=data.get("tax_office", ""),
            phone=data.get("taxpayer_phone", ""),
            bik=data.get("bik", ""),
            account=data.get("account", ""),
            card=data.get("card", ""),
        )
        session.add(profile)
        session.commit()
    finally:
        session.close()

    await _do_calculation(message, state, user)


async def _do_calculation(message: Message, state: FSMContext, user: User):
    data = await state.get_data()
    deduction_type = data.get("deduction_type", "medical")
    total_amount = data.get("total_amount", 0)
    first_payment_date = data.get("first_payment_date", "")

    calculated = calculate_social_deduction(
        deduction_type=deduction_type,
        amount=total_amount,
        institution_name="",
        institution_inn="",
        payment_date=first_payment_date,
    )

    income_val = data.get("income", 0)
    tax_paid_val = data.get("tax_paid", 0)
    tax_base = max(0, income_val - total_amount)
    tax_calculated = round(tax_base * 0.13)
    tax_to_pay = max(0, tax_calculated - round(tax_paid_val))
    tax_return_val = max(0, round(tax_paid_val) - tax_calculated)

    if tax_to_pay > 0:
        result_text = f"💵 К доплате: <b>{tax_to_pay:,} ₽</b>"
    else:
        result_text = f"💵 НДФЛ к возврату: <b>{tax_return_val:,} ₽</b>"

    await message.answer(
        f"📊 Результат расчёта:\n\n"
        f"💰 Сумма расходов: <b>{total_amount:,.2f} ₽</b>\n"
        f"📉 Сумма вычета: <b>{calculated['deduction_amount']:,.2f} ₽</b>\n"
        f"{result_text}\n"
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
        "bik": data.get("bik", ""),
        "account": data.get("account", ""),
        "card": data.get("card", ""),
        "income": income_val,
        "tax_paid": tax_paid_val,
        "tax_to_pay": tax_to_pay,
        "tax_return": tax_return_val,
    }

    await message.answer("⏳ Готовлю декларацию, пара минут...")
    excel_path = await generate_excel(declaration_id, pdf_data)

    session3 = next(get_session())
    try:
        decl = session3.get(Declaration, declaration_id)
        decl.pdf_path = excel_path
        decl.status = "generated"
        session3.commit()
    finally:
        session3.close()

    instruction = _get_instruction(deduction_type)

    await message.answer(
        f"✅ <b>Декларация готова!</b>\n\n{instruction}",
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


def _get_instruction(deduction_type: str) -> str:
    base = (
        "<b>Что делать дальше:</b>\n\n"
        "1. <b>Откройте файл</b> в Excel, проверьте заполненные данные\n"
        "2. <b>Распечатайте</b> следующие листы на А4:\n"
    )

    if deduction_type == "medical":
        base += (
            "   — Титульный лист\n"
            "   — Раздел 1\n"
            "   — Приложение к Разделу 1\n"
            "   — Раздел 2\n"
            "   — Приложение 5 (продолжение)\n"
        )
    elif deduction_type == "education":
        base += (
            "   — Титульный лист\n"
            "   — Раздел 1\n"
            "   — Приложение к Разделу 1\n"
            "   — Раздел 2\n"
            "   — Приложение 5\n"
        )

    base += (
        "3. <b>Подпишите</b> каждый лист (только синей ручкой!)\n"
        "4. <b>Приложите копии документов:</b>\n"
    )

    if deduction_type == "medical":
        base += (
            "   — Справка об оплате медицинских услуг\n"
            "   — Договор с учреждением\n"
            "   — Лицензия учреждения\n"
        )
    elif deduction_type == "education":
        base += (
            "   — Договор на обучение\n"
            "   — Чеки/квитанции об оплате\n"
            "   — Лицензия учебного заведения\n"
        )

    base += (
        "   — Справка о доходах: 2-НДФЛ (для наёмных работников) или справка из приложения «Мой налог» (для самозанятых)\n\n"
        "5. <b>Подайте в налоговую</b> одним из способов:\n"
        "   — Лично в отделении ФНС (запись через nalog.ru)\n"
        "   — Почтой заказным письмом с описью вложения\n\n"
        "⚠️ При открытии файла Excel может показать предупреждения о повреждённых рисунках — "
        "это нормально, данные в ячейках сохранены."
    )

    return base


@router.callback_query(F.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Давайте введём данные заново.")
    await _start_data_input(callback.message, state)
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