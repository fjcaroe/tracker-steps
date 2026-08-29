# Runbook de migración y despliegue — Movilización

**Nada de este runbook se ha ejecutado contra una base real.** Documenta los
pasos para cuando el usuario autorice desplegar; hasta entonces es sólo
referencia. Antes de ejecutar, releer `AUDITORIA_HOMOLOGACION_ODOO_2026-08-24.md`
y `PROMOVER_DEMO_A_DESARROLLO.md` como pide `CLAUDE_SEPARACION_MODULO_MOVILIZACION.md`.

## Orden exacto de instalación/actualización

En **una sola invocación** de `-u`/`-i` (no en pasos separados, para que el
registro de modelos nunca quede sin declarar `step.movi.registry` y afines):

```bash
odoo-bin -u step_hr -i step_mobilization,step_mobilization_agriculture \
  --stop-after-init -d <base>
```

`step_agricultural_access` debe actualizarse en la misma pasada o
inmediatamente después (`-u step_agricultural_access`), ya que ahora depende
de `step_mobilization` y su `agricultural_menu_security.xml` referencia
`step_mobilization.menu_step_mobilization_root`.

## Antes de ejecutar

1. Respaldo: `pg_dump -Fc` de la base + copia del filestore + copia de
   `addons/` con SHA-256 de ambos, en una ruta con fecha.
2. Confirmar en la base real (consulta de sólo lectura) el
   `number_next_actual` de `ir_sequence` donde `code='step_moviliza_seq' AND
   company_id IS NULL` — es el valor que el script de migración va a leer
   para sembrar las secuencias por compañía. Si es 0 o no existe, no hay
   folios históricos que proteger y la siembra es un no-op seguro.
3. Confirmar cuántas filas tiene `product_pricelist` con `moviliza=true` y
   `partner_id` seteado pero `transporte_id` vacío — son las que el
   `post_init_hook` de `step_mobilization_agriculture` va a copiar. Si el
   número es alto, revisar una muestra antes de aplicar.
4. Ejecutar primero en una copia de Desarrollo, nunca en Producción.
5. `--stop-after-init --no-http` primero, revisar el log completo en busca
   de `ERROR`/`CRITICAL`/`Traceback` antes de recién ahí levantar el
   servicio con tráfico.

## Verificación post-instalación

- `step_hr` sigue abriendo y su dashboard de Actividades no reporta error
  aunque `step_mobilization` no estuviera instalado aún en ese momento
  (probar desinstalando temporalmente sólo en la copia de prueba, nunca en
  la base real).
- La app "Movilización" aparece como aplicación de primer nivel, no como
  submenú de Actividades.
- Abrir un viaje existente (si había datos) y confirmar que conserva
  `name`, `date`, pasajeros, costeo y el asiento contable vinculado
  (`invoice_id`) tal como estaban antes de la migración.
- Confirmar que `step_agricultural_access` sigue ocultando/mostrando la app
  Movilización según el grupo `group_app_mobilization` /
  `group_activities_transport` (heredado) para un usuario de prueba.
- Comparar conteos antes/después con el script en `scripts/movilizacion/`
  (ver más abajo) para `step.movi.registry`, `.line`, `.cost.line`,
  `hr.route`, `product.pricelist.move.line`.
- Revisar logs en busca de `ERROR`/`CRITICAL`/`Traceback` nuevos atribuibles
  a `step_mobilization*`.

## Rollback

No ensayado contra una base real (ver limitación en `02_ARQUITECTURA_Y_DECISIONES.md`).
Camino documentado:

1. Restaurar el respaldo de código (`git checkout` al commit previo) y el
   `pg_dump`/filestore tomados en el paso "Antes de ejecutar".
2. No hay una migración inversa automática: el script de step_hr sólo
   reasigna `ir_model_data`, no borra ni recrea tablas, así que restaurar el
   dump completo revierte también esa reasignación sin pasos adicionales.
3. Reiniciar sólo el servicio del ambiente afectado.

## Script de auditoría de datos (plantilla, no ejecutado)

Guardar como `scripts/movilizacion/auditoria_datos.sql` y correr con
`psql -f` contra una base real autorizada (nunca producción como primer
ambiente), antes y después de la migración, para el "Reporte de datos
antes/después" (entregable #5):

```sql
select company_id, state, count(*) from step_movi_registry group by 1,2 order by 1,2;
select count(*) from step_movi_registry_line;
select count(*) from step_movi_cost_line;
select company_id, count(*) from hr_route group by 1;
select count(*) from product_pricelist_move_line;
select count(*) from step_movi_registry r
  where r.fundo_id is null or r.recorrido_id is null or r.vehicle_id is null
     or r.partner_id is null or r.chofer_id is null; -- huérfanos/incompletos
select count(*) from step_movi_registry where invoice_id is not null
  and invoice_id not in (select id from account_move); -- referencias inválidas
```

## Retiro de aliases

No hay período de convivencia de XML IDs externos: el único consumidor
externo detectado (`step_agricultural_access.menu_step_moviliza`) ya se
actualizó en este mismo commit para usar el ID nuevo, así que no queda
ningún alias temporal pendiente de retirar más adelante.
