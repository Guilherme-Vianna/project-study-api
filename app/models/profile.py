from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column


class PersonProfileMixin:
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(150))
    birth_date: Mapped[date | None] = mapped_column(Date)
    postal_code: Mapped[str | None] = mapped_column(String(8))
    mobile_phone: Mapped[str | None] = mapped_column(String(16))
