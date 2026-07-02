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
from core.generator.pdf_generator import generate_pdf
from core.generator.xml_generator import generate_xml
from sqlalchemy import select

router = Router()


class UploadStates(StatesGroup):
    waiting_for_file = State()
    waiting_for_photo = State()
    waiting_for_manual_name = State()
    waiting_for_manual_inn = State()
    waiting_for_manual_amount = State()


@router.callback_query(F.data == "menu_upload")
async def start_upload(callback: CallbackQuery, state: FSMContext):
    user: User = callback.middleware_data.get("user")
    if not user:
        await callback.answer("Ошибка")
        return

    # Проверка лимитов
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
async def handle_file(message: Message, state: FSMContext):
    user: User = message.middleware_data.get("user")
    if not user:
        await message.answer("Ошибка. Попробуйте позже.")
        return

    document = message.document
    file_name = document.file_name.lower()

    # Проверка формата
    if not (file_name.endswith(".pdf") or file_name.endswith(".xlsx") or file_name.endswith(".xls")):
        await message.answer("❌ Поддерживаются только PDF и Excel файлы. Отправьте файл ещё раз.")
        return

    # Скачиваем файл
    os.makedirs(DATA_TEMP_DIR, exist_ok=True)
    file_id = document.file_id
    file = await message.bot.get_file(file_id)
    file_ext = file_name.split(".")[-1]
    temp_path = os.path.join(DATA_TEMP_DIR, f"{uuid.uuid4()}.{file_ext}")
    await message.bot.download_file(file.file_path, temp_path)

    await message.answer("🔍 Анализирую выписку...")

    # Парсинг
    try:
        if file_ext == "pdf":
            parsed_payments = await parse_pdf(temp_path)
        else:
            # Excel — пока заглушка
            await message.answer("⚠️ Обработка Excel пока в разработке. Отправьте PDF.")
            os.remove(temp_path)
            await state.clear()
            return
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

    # Группируем найденные платежи по категориям
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
async def handle_deduction_choice(callback: CallbackQuery, state: FSMContext):
    user: User = callback.middleware_data.get("user")
    if not user:
        await callback.answer("Ошибка")
        return

    deduction_type = callback.data.replace("deduction_", "")
    # Пока поддерживаем только medical и education
    if deduction_type not in ("medical", "education"):
        await callback.answer("Этот тип вычета пока в разработке", show_alert=True)
        return

    # Берём данные из предыдущего шага
    # (в реальном сценарии данные придут из FSM, пока упрощённо)
    await callback.message.edit_text(
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

    # Скачиваем фото
    os.makedirs(DATA_TEMP_DIR, exist_ok=True)
    photo = message.photo[-1]
    file = await message.bot.get_file(photo.file_id)
    temp_path = os.path.join(DATA_TEMP_DIR, f"{uuid.uuid4()}.jpg")
    await message.bot.download_file(file.file_path, temp_path)

    # OCR — пока заглушка
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
    await state.set_state(UploadStates.waiting_for_photo)  # остаёмся в этом состоянии для confirm


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
    await state.set_state(UploadStates.waiting_for_photo)


@router.callback_query(F.data == "confirm_yes")
async def confirm_yes(callback: CallbackQuery, state: FSMContext):
    user: User = callback.middleware_data.get("user")
    if not user:
        await callback.answer("Ошибка")
        return

    data = await state.get_data()
    deduction_type = data.get("deduction_type", "medical")
    institution_name = data.get("institution_name", "")
    institution_inn = data.get("institution_inn", "")
    total_amount = data.get("total_amount", 0)

    # Расчёт вычета
    calculated = calculate_social_deduction(
        deduction_type=deduction_type,
        amount=total_amount,
        institution_name=institution_name,
        institution_inn=institution_inn
    )

    await callback.message.edit_text(
        f"📊 Результат расчёта:\n\n"
        f"🏢 Учреждение: <b>{institution_name}</b>\n"
        f"💰 Сумма расходов: <b>{total_amount:,.2f} ₽</b>\n"
        f"📉 Сумма вычета: <b>{calculated['deduction_amount']:,.2f} ₽</b>\n"
        f"💵 НДФЛ к возврату: <b>{calculated['tax_return']:,.2f} ₽</b>\n"
        f"📆 Год: <b>{calculated['year']}</b>"
    )

    # Сохраняем декларацию в БД
    session_gen = get_session()
    session = await anext(session_gen)
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
        await session.commit()
        await session.refresh(declaration)
        declaration_id = declaration.id
    finally:
        await session.close()

    if user.access_type == ACCESS_DEMO and user.telegram_id not in ADMIN_IDS:
        # Демо — только расчёт
        user.declarations_used += 1
        session_gen2 = get_session()
        session2 = await anext(session_gen2)
        try:
            await session2.merge(user)
            await session2.commit()
        finally:
            await session2.close()

        await callback.message.answer(
            "⚠️ У вас демо-доступ. Скачивание PDF и XML недоступно.\n"
            "Для получения полного доступа свяжитесь с администратором."
        )
    else:
        # Генерируем PDF и XML
        pdf_path = await generate_pdf(declaration_id, calculated)
        xml_path = await generate_xml(declaration_id, calculated)

        session_gen3 = get_session()
        session3 = await anext(session_gen3)
        try:
            decl = await session3.get(Declaration, declaration_id)
            decl.pdf_path = pdf_path
            decl.xml_path = xml_path
            decl.status = "generated"
            await session3.commit()
        finally:
            await session3.close()

        await callback.message.answer(
            "✅ Декларация готова! Выберите формат для скачивания:",
            reply_markup=download_kb(declaration_id)
        )

        # Обновляем счётчик
        user.declarations_used += 1
        session_gen4 = get_session()
        session4 = await anext(session_gen4)
        try:
            await session4.merge(user)
            await session4.commit()
        finally:
            await session4.close()

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "confirm_no")
async def confirm_no(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text("Давайте введём данные заново.")
    await state.set_state(UploadStates.waiting_for_manual_name)
    await callback.message.answer("Введите наименование учреждения:")
    await callback.answer()


@router.callback_query(F.data.startswith("download_"))
async def download_file(callback: CallbackQuery):
    user: User = callback.middleware_data.get("user")
    if not user:
        await callback.answer("Ошибка")
        return

    if user.access_type == ACCESS_DEMO and user.telegram_id not in ADMIN_IDS:
        await callback.answer("Скачивание недоступно в демо-режиме", show_alert=True)
        return

    _, file_type, decl_id = callback.data.split("_", 2)
    decl_id = int(decl_id)

    session_gen = get_session()
    session = await anext(session_gen)
    try:
        declaration = await session.get(Declaration, decl_id)
        if not declaration:
            await callback.answer("Декларация не найдена")
            return

        file_path = declaration.pdf_path if file_type == "pdf" else declaration.xml_path
        if not file_path or not os.path.exists(file_path):
            await callback.answer("Файл не найден")
            return

        await callback.message.answer_document(FSInputFile(file_path))
    finally:
        await session.close()

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