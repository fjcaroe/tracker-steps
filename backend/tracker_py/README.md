# Tracker Steps API

Backend FastAPI consumido por Web Tracker y por la sincronización del módulo
Odoo `step_hr`.

## Desarrollo

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest
```

Requiere `DATABASE_URL` y `JWT_SECRET` en un archivo `.env` local. Ese archivo
no se versiona.

## Migraciones

Las migraciones SQL están en `migrations/` y son idempotentes. Deben ejecutarse
contra la base `tracker_steps` antes de reiniciar una versión nueva de la API.

La migración `20260820_master_crud.sql` agrega desactivación lógica a
implementos. Conductores, actividades y labores ya contaban con `is_active`.
