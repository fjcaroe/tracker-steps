from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.security import get_current_user, require_admin_for_master_write

from app.routers.health import router as health_router
from app.routers.auth import router as auth_router
from app.routers.activities import router as activities_router
from app.routers.labors import router as labors_router
from app.routers.implements import router as implements_router
from app.routers.work_orders import router as work_orders_router
from app.routers.machines import router as machines_router
from app.routers.drivers import router as drivers_router
from app.routers.cost_centers import router as cost_centers_router
from app.routers.fields import router as fields_router
from app.routers.sessions import router as sessions_router
from app.routers.lots import router as lots_router
from app.routers.regions import router as regions_router
from app.routers.communes import router as communes_router
from app.routers.fundos import router as fundos_router
from app.routers.sectors import router as sectors_router
from app.routers.species import router as species_router
from app.routers.varieties import router as varieties_router

app = FastAPI(title="Tracker Steps API")

app.include_router(health_router)
app.include_router(auth_router)
# Los catálogos y la operación productiva nunca deben quedar expuestos sin sesión.
# El control por centro de costo se aplica además en los recursos transaccionales.
protected = [Depends(get_current_user)]
protected_master = [Depends(require_admin_for_master_write)]
app.include_router(activities_router, dependencies=protected_master)
app.include_router(labors_router, dependencies=protected_master)
app.include_router(implements_router, dependencies=protected_master)
app.include_router(work_orders_router, dependencies=protected)
app.include_router(machines_router, dependencies=protected_master)
app.include_router(drivers_router, dependencies=protected_master)
app.include_router(cost_centers_router, dependencies=protected_master)
app.include_router(regions_router, dependencies=protected_master)
app.include_router(communes_router, dependencies=protected_master)
app.include_router(fundos_router, dependencies=protected_master)
app.include_router(sectors_router, dependencies=protected_master)
app.include_router(species_router, dependencies=protected_master)
app.include_router(varieties_router, dependencies=protected_master)
app.include_router(fields_router, dependencies=protected_master)
app.include_router(sessions_router)
app.include_router(lots_router, dependencies=protected)
