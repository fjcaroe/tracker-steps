from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Este PostgreSQL también atiende varias instancias de Odoo. El pool por
# defecto de SQLAlchemy podía abrir hasta 15 conexiones durante la carga en
# paralelo de Maestros, agotando los 100 cupos del servidor compartido.
# Tres conexiones máximas son suficientes para estas consultas cortas; las
# solicitudes restantes esperan brevemente en vez de provocar errores 500.
if settings.DATABASE_URL.startswith("sqlite"):
    # Entorno local y pruebas: SQLite no admite las opciones del pool PostgreSQL.
    engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=1,
        pool_timeout=15,
        pool_recycle=300,
        pool_use_lifo=True,
        connect_args={"application_name": "steps_tracker_api"},
    )

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
