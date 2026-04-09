from sqlalchemy import Column, Integer, String, Boolean
from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=True)
    is_pro = Column(Boolean, default=False, nullable=False)
    stripe_customer_id = Column(String, nullable=True)