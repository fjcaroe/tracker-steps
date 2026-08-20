
from app.db.base import Base

from sqlalchemy import Column, Integer, String, Text, Boolean, TIMESTAMP, ForeignKey, Numeric

class Machine(Base):
    __tablename__ = "machines"

    id = Column(Integer, primary_key=True)
    external_id = Column(String(64))
    name = Column(Text, nullable=False)
    plate = Column(String(32))
    description = Column(Text)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"))
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True))

    tank_capacity_liters = Column(Numeric(10, 2))

    # unidad: 'lph' o 'kmpl'
    fuel_consumption_unit = Column(String(8), nullable=False, default="lph")

    # valores posibles según unidad
    fuel_consumption_lph = Column(Numeric(10, 2))
    fuel_efficiency_kmpl = Column(Numeric(10, 4))

    # antiguo (si decides dejarlo)
    fuel_consumption_lpkm = Column(Numeric(10, 3))

    default_activity_id = Column(Integer, ForeignKey("activities.id"))
    default_labor_id = Column(Integer, ForeignKey("labors.id"))
