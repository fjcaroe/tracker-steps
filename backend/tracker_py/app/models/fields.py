from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.db.base import Base


class Field(Base):
    __tablename__ = "fields"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(Text, nullable=False)
    cost_center_id = Column(Integer, ForeignKey("cost_centers.id"), nullable=True)
    color = Column(Text, nullable=True)
    polygon = Column(JSONB, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now())
    species_id = Column(Integer, ForeignKey("species.id"))
    variety_id = Column(Integer, ForeignKey("varieties.id"))

    species = relationship("Species")
    variety = relationship("Variety")

    cost_center = relationship("CostCenter")
