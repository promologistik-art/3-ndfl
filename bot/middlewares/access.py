from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from bot.config import ADMIN_IDS, ACCESS_DEMO, ACCESS_UNLIMITED, ACCESS_MONTHLY, ACCESS_TEST_14
from core.models import get_session, User


class AccessMiddleware(BaseMiddleware):

    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        user_tg = event.from_user
        if not user_tg:
            return await handler(event, data)

        session = next(get_session())
        try:
            result = session.execute(
                select(User).where(User.telegram_id == user_tg.id)
            )
            user = result.scalar_one_or_none()

            if not user:
                user = User(
                    telegram_id=user_tg.id,
                    username=user_tg.username,
                    first_name=user_tg.first_name,
                    last_name=user_tg.last_name,
                    access_type=ACCESS_DEMO,
                    declarations_used=0
                )
                session.add(user)
                session.commit()
                session.refresh(user)

                # Уведомление админам
                bot = data.get("bot")
                if bot:
                    for admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(
                                admin_id,
                                f"🆕 Новый пользователь: @{user_tg.username or 'нет username'} "
                                f"({user_tg.first_name or ''} {user_tg.last_name or ''})"
                            )
                        except Exception:
                            pass

            if user.telegram_id in ADMIN_IDS:
                user.access_type = ACCESS_UNLIMITED
                session.commit()

            if user.access_type == ACCESS_MONTHLY and user.access_expires:
                now = datetime.now(timezone.utc)
                if user.access_expires.replace(tzinfo=timezone.utc) < now:
                    user.access_type = ACCESS_DEMO
                    user.declarations_used = 0
                    session.commit()

            if user.access_type == ACCESS_TEST_14 and user.access_expires:
                now = datetime.now(timezone.utc)
                if user.access_expires.replace(tzinfo=timezone.utc) < now:
                    user.access_type = ACCESS_DEMO
                    user.declarations_used = 0
                    session.commit()

            data["user"] = user
        finally:
            session.close()

        return await handler(event, data)