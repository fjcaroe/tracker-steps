from fastapi import APIRouter

router = APIRouter(tags=["health"])

@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/health/capabilities")
def capabilities():
    return {
        "status": "ok",
        "api_version": "2026.08.20",
        "capabilities": [
            "odoo_sync_v1",
            "master_drivers_crud",
            "master_activities_crud",
            "master_labors_crud",
            "master_implements_crud",
            "master_fields_polygon_crud",
            "work_orders_manual_crud",
        ],
    }
