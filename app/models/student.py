from app.models.base import Base, TimestampMixin, UUIDv7PrimaryKeyMixin
from app.models.history import versioned
from app.models.profile import PersonProfileMixin


@versioned
class Student(UUIDv7PrimaryKeyMixin, PersonProfileMixin, TimestampMixin, Base):
    __tablename__ = "students"
