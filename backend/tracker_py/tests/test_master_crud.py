from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Registra todos los modelos y relaciones igual que el arranque productivo.
from app.main import app as production_app
from app.db.base import Base
from app.db.session import get_db
from app.models.activities import Activity, Labor
from app.models.drivers import Driver
from app.models.implements import Implement
from app.routers.activities import router as activities_router
from app.routers.drivers import router as drivers_router
from app.routers.implements import router as implements_router
from app.routers.labors import router as labors_router


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app = FastAPI()
app.include_router(drivers_router)
app.include_router(implements_router)
app.include_router(activities_router)
app.include_router(labors_router)
app.dependency_overrides[get_db] = override_db
client = TestClient(app)


def setup_function():
    Base.metadata.drop_all(engine, tables=[Labor.__table__, Activity.__table__, Driver.__table__, Implement.__table__])
    Base.metadata.create_all(engine, tables=[Activity.__table__, Labor.__table__, Driver.__table__, Implement.__table__])


def test_openapi_exposes_full_master_contract():
    paths = app.openapi()["paths"]
    assert {"patch", "delete"} <= set(paths["/drivers/{driver_id}"])
    assert {"put", "delete"} <= set(paths["/activities/{activity_id}"])
    assert {"put", "delete"} <= set(paths["/labors/{labor_id}"])
    assert {"patch", "delete"} <= set(paths["/implements/{implement_id}"])


def test_production_app_advertises_release_capabilities():
    production_client = TestClient(production_app)
    response = production_client.get("/health/capabilities")
    assert response.status_code == 200
    advertised = set(response.json()["capabilities"])
    assert {
        "odoo_sync_v1",
        "master_drivers_crud",
        "master_activities_crud",
        "master_labors_crud",
        "master_implements_crud",
    } <= advertised


def test_work_order_output_contract_includes_machine_and_final_fuel():
    schema = production_app.openapi()["components"]["schemas"]["WorkOrderOut"]
    assert "machine_id" in schema["properties"]
    assert "fuel_tank_end_liters" in schema["properties"]
    assert "machine_id" in schema["required"]
    assert {"type": "null"} in schema["properties"]["machine_id"]["anyOf"]


def test_driver_can_be_created_edited_and_soft_deleted():
    created = client.post("/drivers", json={"name": "Ana", "rut": "1-9"})
    assert created.status_code == 200
    driver_id = created.json()["id"]

    updated = client.patch(f"/drivers/{driver_id}", json={"name": "Ana Pérez"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Ana Pérez"

    assert client.delete(f"/drivers/{driver_id}").status_code == 200
    assert client.get("/drivers").json() == []
    inactive = client.get("/drivers?include_inactive=true").json()
    assert inactive[0]["is_active"] is False


def test_implement_can_be_edited_soft_deleted_and_reactivated():
    created = client.post("/implements", json={"name": "Rastra"})
    implement_id = created.json()["id"]

    updated = client.patch(f"/implements/{implement_id}", json={"name": "Rastra liviana"})
    assert updated.status_code == 200
    assert updated.json()["name"] == "Rastra liviana"

    assert client.delete(f"/implements/{implement_id}").status_code == 200
    assert client.get("/implements").json() == []
    reactivated = client.post("/implements", json={"name": "Rastra liviana"})
    assert reactivated.json()["id"] == implement_id
    assert reactivated.json()["is_active"] is True


def test_activity_and_labor_delete_preserves_records_as_inactive():
    activity = client.post("/activities", json={"name": "Aplicaciones", "code": "APL"}).json()
    labor = client.post(
        "/labors",
        json={"activity_id": activity["id"], "name": "Aplicación foliar", "code": "FOL"},
    ).json()

    assert client.delete(f"/labors/{labor['id']}").status_code == 200
    assert client.delete(f"/activities/{activity['id']}").status_code == 200
    assert client.get("/labors").json() == []
    assert client.get("/activities").json() == []

    with TestingSession() as db:
        assert db.get(Labor, labor["id"]).is_active is False
        assert db.get(Activity, activity["id"]).is_active is False
