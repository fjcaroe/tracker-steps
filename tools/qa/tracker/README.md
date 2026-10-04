# Validaciones recuperadas de Tracker

Recuperadas de archivos locales el 03-10-2026 y asociadas a esta rama.

- `tracker-preflight.sh`: inspección de configuración de Odoo y módulos en el servidor.
- `tracker-final-http.sh`: compara el JS servido por los portales con el instalado.
- `tracker-live-api-check.py`: comprueba aislamiento entre empresas usando claves locales del servidor; no imprime tokens ni claves. Se quitó la expectativa antigua de que todos los activos carezcan de GPS real.
- `tracker-navigation-http-check.py`: ejecutar mediante Odoo shell. Sesión transitoria, consultas de navegación y rechazos esperados de peticiones inválidas. Se quitó la ejecución del cron de sincronización; cerrar la sesión y rollback no revierten escrituras efectuadas por otro proceso HTTP.
- `tracker-pg-constraints.py`: requiere `TRACKER_QA_DATABASE` con prefijo `TRACKER_QA_` o `TRACKER_LAYOUT_QA_`; comprueba restricciones y siempre hace rollback. Solo contra una copia QA preparada.

No son pasos automáticos de despliegue. Revisar puertos, módulos y contexto del entorno antes de ejecutarlos. Las claves siguen fuera de Git. Las versiones anteriores de estos checks y las previews locales quedaron en el respaldo privado por estar reemplazadas por estas validaciones o por el mock portal versionado.
