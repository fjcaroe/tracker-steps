from sqlalchemy import Column, Integer, String, Text, Numeric, TIMESTAMP, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base

class Region(Base):
    __tablename__ = "regions"
    id = Column(Integer, primary_key=True)
    code = Column(String(16))
    name = Column(Text, nullable=False, unique=True)
    created_at = Column(TIMESTAMP(timezone=True))

class Commune(Base):
    __tablename__ = "communes"
    id = Column(Integer, primary_key=True)
    region_id = Column(Integer, ForeignKey("regions.id"), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True))

    region = relationship("Region")

class Fundo(Base):
    __tablename__ = "fundos"
    id = Column(Integer, primary_key=True)
    external_id = Column(String(64))
    name = Column(Text, nullable=False, unique=True)
    commune_id = Column(Integer, ForeignKey("communes.id"))
    address = Column(Text)
    hectares_total = Column(Numeric(10, 2))
    created_at = Column(TIMESTAMP(timezone=True))

    commune = relationship("Commune")
    sectors = relationship("Sector", back_populates="fundo")

class Sector(Base):
    __tablename__ = "sectors"
    id = Column(Integer, primary_key=True)
    external_id = Column(String(64))
    fundo_id = Column(Integer, ForeignKey("fundos.id"), nullable=False)
    name = Column(Text, nullable=False)
    sdp_code = Column(String(32))
    hectares_total = Column(Numeric(10, 2))
    created_at = Column(TIMESTAMP(timezone=True))

    fundo = relationship("Fundo", back_populates="sectors")
