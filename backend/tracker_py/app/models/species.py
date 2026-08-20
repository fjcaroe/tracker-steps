from sqlalchemy import Column, Integer, Text, TIMESTAMP, ForeignKey, Table
from sqlalchemy.orm import relationship
from app.db.base import Base

cost_center_varieties = Table(
    "cost_center_varieties",
    Base.metadata,
    Column("cost_center_id", Integer, ForeignKey("cost_centers.id", ondelete="CASCADE"), primary_key=True),
    Column("variety_id", Integer, ForeignKey("varieties.id", ondelete="RESTRICT"), primary_key=True),
    Column("created_at", TIMESTAMP(timezone=True)),
)

class Species(Base):
    __tablename__ = "species"
    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False, unique=True)
    created_at = Column(TIMESTAMP(timezone=True))

    varieties = relationship("Variety", back_populates="species")

class Variety(Base):
    __tablename__ = "varieties"
    id = Column(Integer, primary_key=True)
    species_id = Column(Integer, ForeignKey("species.id"), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True))

    species = relationship("Species", back_populates="varieties")
    cost_centers = relationship("CostCenter", secondary=cost_center_varieties, back_populates="varieties")
