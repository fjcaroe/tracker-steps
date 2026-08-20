from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey, Numeric, Date, func
from sqlalchemy.orm import relationship

from app.db.base import Base


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True)
    code = Column(Text, nullable=False)
    work_date = Column(Date, nullable=False)
    season = Column(Text, nullable=False)

    activity_id = Column(Integer, ForeignKey("activities.id"), nullable=False)
    labor_id = Column(Integer, ForeignKey("labors.id"), nullable=False)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"))
    field_id = Column(Integer, ForeignKey("fields.id"))
    machine_id = Column(Integer, ForeignKey("machines.id"))

    notes = Column(Text)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())

    implement_id = Column(Integer, ForeignKey("implements.id"))
    hourmeter_initial = Column(Numeric(10, 2))
    hourmeter_final = Column(Numeric(10, 2))
    fuel_tank_start_liters = Column(Numeric(10, 2))
    fuel_refill_liters = Column(Numeric(10, 2))
    fuel_tank_end_liters = Column(Numeric(10, 2))

    activity = relationship("Activity")
    labor = relationship("Labor")
    cost_center = relationship("CostCenter")
    field = relationship("Field")
    implement = relationship("Implement")
