from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

load_dotenv()

# Por defecto usa SQLite si no hay URL de Postgres configurada
# Vercel usa "POSTGRES_URL", "POSTGRES_PRISMA_URL", etc. Intentamos leer POSTGRES_URL si DATABASE_URL falla.
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    DATABASE_URL = os.getenv("POSTGRES_URL")

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./crm.db"

# Fix para SQLAlchemy que removió soporte para 'postgres://' (Vercel lo usa por defecto)
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
