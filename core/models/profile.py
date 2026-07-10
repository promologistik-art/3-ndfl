from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from core.models.base import Base


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # метка: "Иванов И.И."
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    passport: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tax_office: Mapped[str | None] = mapped_column(String(4), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bik: Mapped[str | None] = mapped_column(String(9), nullable=True)
    account: Mapped[str | None] = mapped_column(String(20), nullable=True)
    card: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())