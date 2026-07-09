from datetime import datetime
from sqlalchemy import BigInteger, String, Integer, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column
from core.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    middle_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    inn: Mapped[str | None] = mapped_column(String(12), nullable=True)
    birth_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    passport: Mapped[str | None] = mapped_column(String(10), nullable=True)
    tax_office: Mapped[str | None] = mapped_column(String(4), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    access_type: Mapped[str] = mapped_column(String(20), default="demo")
    access_expires: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    declarations_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())