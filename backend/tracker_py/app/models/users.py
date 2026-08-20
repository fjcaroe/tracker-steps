from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey, func

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())


class UserCostCenter(Base):
    __tablename__ = "user_cost_centers"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id", ondelete="CASCADE"), primary_key=True)
