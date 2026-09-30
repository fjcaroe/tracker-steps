from app.db.session import SessionLocal
from app.routers.fleet import check_communications

with SessionLocal() as db:
    check_communications(db)
