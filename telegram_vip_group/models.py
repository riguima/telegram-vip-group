from datetime import date, datetime, timedelta

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from telegram_vip_group.database import db


class Base(DeclarativeBase):
    pass


class Payment(Base):
    __tablename__ = 'payments'
    id: Mapped[int] = mapped_column(primary_key=True)
    payment_id: Mapped[int]
    payment_datetime: Mapped[datetime] = mapped_column(default=datetime.now())
    user_id: Mapped[str]
    chat_index: Mapped[int]


class Client(Base):
    __tablename__ = 'clients'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str]


class Signature(Base):
    __tablename__ = 'signatures'
    id: Mapped[int] = mapped_column(primary_key=True)
    chat_id: Mapped[str]
    user_id: Mapped[str]
    end_date: Mapped[date] = mapped_column(
        default=date.today() + timedelta(days=7)
    )


Base.metadata.create_all(db)
