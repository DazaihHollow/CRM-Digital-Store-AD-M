from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base

class Prospect(Base):
    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    industry = Column(String, nullable=True) # Rubro
    contact_name = Column(String, nullable=True)
    email = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    status = Column(String, default="Nuevo") # Nuevo, Contactado, Interesado, Cliente
    address = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    notes = relationship("Note", back_populates="prospect")

class Note(Base):
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    prospect_id = Column(Integer, ForeignKey("prospects.id"))

    prospect = relationship("Prospect", back_populates="notes")
