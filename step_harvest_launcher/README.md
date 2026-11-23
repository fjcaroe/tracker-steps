# Steps Harvest launcher

This is a separate Odoo application entry for the Steps Harvest web app. It
opens `/harvest/open` in a new tab, which redirects to this database's
canonical HTTPS `/cosecha/` PWA. It also redirects legacy direct-port
`/cosecha` URLs. It does not rename or replace the Odoo Cosecha module.

Install only on instances where Nginx serves `/cosecha/` and Odoo exposes
`/api/harvest/`. Set `steps.harvest.url` to the database's full HTTPS
Harvest URL. The launcher has been installed on `STEPS_DEMO`,
`LAB_TAREAS`, and `CERRO_EL_PLOMO`. Cerro El Plomo also serves the Task PWA
at `/task/`. Other databases need their own web/API deployment first.
