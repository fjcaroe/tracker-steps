# Helpdesk 20 y 21 Panel de nómina

Los tickets 20 y 21 forman una sola mejora funcional del panel de Nómina. El
ticket 20 define el resumen de imposiciones desde el TXT PreviRed consolidado;
el ticket 21 actualiza la presentación y fija los indicadores sobre el Total
Haberes oficial del Libro DT.

## Fuentes

- Sueldo base: código DT 2101.
- Total haberes: código DT 5201. Reemplaza el valor imponible 5210 mostrado
  anteriormente.
- Sueldo líquido: código DT 5501.
- Anticipos y retenciones: código DT 3188.
- Cotización trabajador: campos PreviRed 28, 70, 80, 81, 90, 85, 22, 30, 43
  y 101.
- Cotización empresa: campos PreviRed 29, 94, 95, 71, 98 y 102.
- Imposiciones pagadas: cotización trabajador más cotización empresa.

Cada porcentaje de la tabla se calcula sobre el Total Haberes DT 5201. El
indicador adicional de costo seguros solicitado en el ticket 20 se conserva y
usa `cotización empresa / (total haberes - asignación familiar DT 2311)`.

## Validación de referencia

En Demo-Sys, EMCA agosto 2026 tiene 82 liquidaciones cerradas. El dataset del
Libro DT confirma sueldo base 49.897.767, total haberes 67.461.124, líquido
47.361.257 y anticipos 4.570.000, coincidentes con el documento (diferencia de
un peso en el líquido por el estado actual de la base).

El TXT PreviRed real entrega cotización trabajador 15.710.705, cotización
empresa 3.797.293 e imposiciones pagadas 19.507.998. Los indicadores resultan:
sueldo base 74,0 %, líquido 70,2 %, anticipos 6,8 %, empresa 5,6 %, trabajador
23,3 %, pagado 28,9 % y costo de seguros 5,65 %.

## Despliegue

`step_hr_remuneration_book 18.0.3.4.0` quedó actualizado con dos pruebas
dirigidas sin fallos, servicios activos y HTTP 200 en:

- Desarrollo / `LAB_TAREAS`. Respaldo:
  `/opt/steps_backups/ticket20_21_payroll_dashboard_20260910-012537/dev`.
- Demo / `STEPS_DEMO`. Respaldo:
  `/opt/steps_backups/ticket20_21_payroll_dashboard_20260910-012616/demo`.
- Demo-Sys / `STEPS_DEMO_SYS`. Respaldo:
  `/opt/steps_backups/ticket20_21_payroll_dashboard_20260910-011855/demosys`.
