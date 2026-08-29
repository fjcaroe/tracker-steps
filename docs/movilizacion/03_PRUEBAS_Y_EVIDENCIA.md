# Pruebas ejecutadas y evidencia

## 1. Estáticas (Fase 8.1)

Ejecutadas directamente en este checkout, sin necesidad de Odoo:

- Compilación Python de los 3 addons tocados (`step_mobilization`,
  `step_mobilization_agriculture`, `step_hr`) + `step_agricultural_access`:
  **100 archivos, 0 errores**.
- Parseo XML de bien-formado de los 4 addons: **80 archivos, 0 errores**.
- Verificación de que cada archivo listado en `data`/`demo`/`assets` de cada
  manifiesto existe en disco: **OK en los 3 addons**.
- Verificación cruzada de XML IDs internos (`ref=`/`inherit_id=`/`model_id:id=`
  del CSV de accesos contra los modelos realmente declarados): sin
  referencias colgantes.
- Grep exhaustivo confirmando que ningún campo movido (`is_movi`,
  `moviliza`, `step_trans_person`, `step_chofer`, `transpor_id`,
  `step_min_pass`, `step_max_pass`, `step_movi_journal_id`,
  `step_movi_document_type_id`, `move_item`, `transporte_id`) sigue
  declarado o referenciado activamente en `step_hr` (sólo quedan menciones
  dentro de comentarios XML, verificado línea por línea).

## 2. Instalación real en Odoo 18 Community (Docker, local, descartable)

No hay Odoo instalable en este equipo salvo por Docker (ver limitación en
`02_ARQUITECTURA_Y_DECISIONES.md §7`). Se levantó Postgres 16 + la imagen
oficial `odoo:18.0` en una red Docker local, sin tocar ninguna base remota:

```bash
docker network create step_mobilization_test_net
docker run -d --name step_mob_test_pg --network step_mobilization_test_net \
  -e POSTGRES_USER=odoo -e POSTGRES_PASSWORD=odoo -e POSTGRES_DB=postgres postgres:16
docker run --rm --network step_mobilization_test_net \
  -e HOST=step_mob_test_pg -e USER=odoo -e PASSWORD=odoo \
  -v <ruta_local>/step_mobilization:/mnt/extra-addons/step_mobilization \
  odoo:18.0 odoo -i step_mobilization --stop-after-init --without-demo=all \
  -d step_mob_testdb
```

**Resultado: `step_mobilization` instala limpio en Odoo 18 Community**, sin
`step_hr` (confirma la independencia de dependencias buscada). Se probaron
además, sobre la misma base:

- **Actualización idempotente** (`-u step_mobilization` sobre la base ya
  instalada): sin errores, tabla intacta.
- **Suite de tests automatizados** (`--test-enable --test-tags
  /step_mobilization`): **16 tests, 0 fallos, 0 errores** tras corregir los
  bugs que la propia corrida encontró (ver §3).
- **Desinstalación controlada** (`button_immediate_uninstall` vía `odoo
  shell`, sólo en esta base descartable): sin errores; la base sigue
  arrancando después.

Todo el proceso corrió contra contenedores locales efímeros, eliminados al
finalizar (`docker rm`/`docker network rm`); en ningún momento se usó una
base ni un servidor remoto.

### Limitación: no se pudo instalar `step_mobilization_agriculture` en este entorno

`step_mobilization_agriculture` depende de `step_hr`, y `step_hr` depende a
su vez de módulos Enterprise (`hr_holidays_gantt`, `hr_work_entry_holidays`,
`hr_payroll`, `hr_work_entry_contract_enterprise`) que no existen en la
imagen Community usada para esta prueba y que este entorno no tiene licencia
para instalar. Por eso, para `step_mobilization_agriculture` sólo se pudo
validar lo estático (compilación, XML, referencias cruzadas) — la
instalación real contra un Odoo con Enterprise queda pendiente de un entorno
con esa licencia (el mismo servidor de producción sí la tiene, según
`docs/DEPLOY_WEB_TRACKER.md`, pero no se toca sin autorización).

## 3. Bugs reales encontrados y corregidos por estas pruebas

La corrida en Odoo real (no la revisión estática) encontró y permitió
corregir cuatro problemas que ningún linter habría detectado:

1. **Filtro "Sobrecupo" no buscable**: `overcapacity` era un campo
   computado sin `store=True`, usado en un `<filter>` de búsqueda — Odoo
   rechaza la vista al cargar. Corregido: `overcapacity`,
   `boarded_count`, `aboard_count` y `alighted_count` ahora se computan
   juntos y todos con `store=True` (evita además el segundo bug).
2. **Advertencia de "store" inconsistente**: iba a producir recómputos
   silenciosos incorrectos entre campos de un mismo método con distinto
   `store`. Corregido junto con el punto anterior.
3. **`dict(field.selection)` sobre un campo `related`**: en Odoo 18 el
   descriptor de un `Selection` `related` no siempre expone `.selection`
   como lista iterable directamente; usarlo así rompía la congelación de
   tarifas del contrato (`_freeze_rate_snapshot`). Corregido con un mapeo
   local de las 3 opciones reales (`ida`/`vuelta`/`ida_vuelta`).
4. **Idempotencia de marcaciones silenciosamente rota si `device_id` es
   nulo**: el `unique(trip_id, device_id, idempotency_key)` no bloquea
   duplicados cuando `device_id` es `NULL`, porque Postgres no considera dos
   `NULL` iguales. Se detectó porque el test de duplicados no fallaba como
   se esperaba. Corregido haciendo `device_id` obligatorio en
   `step.mobilization.passenger.event` y `step.mobilization.gps.point` —
   coherente además con que ambos modelos sólo tienen sentido de negocio si
   vienen de un dispositivo autenticado.
5. **Tarifa "ida y vuelta" duplicada**: el costeo aplicaba la tarifa
   completa tanto a la entrada como a la salida cuando `cobro_type ==
   'ida_vuelta'`, cobrando el doble a un pasajero que sube y baja en el
   mismo viaje. Corregido: para `ida_vuelta` la tarifa se reparte a la mitad
   entre ida y vuelta (una tarifa = un viaje redondo, no dos tarifas).

## 4. Suite de tests de dominio (Fase 8.2) — cobertura actual

`step_mobilization/tests/`: 16 tests, todos verdes en la corrida anterior.

- `test_registry.py`: tarifa faltante levanta error; costeo no duplica
  líneas al recalcular; costeo divide por pasajeros únicos (no por líneas
  duplicadas de entrada/salida — el bug histórico de step_hr); sobrecupo se
  detecta; cancelar exige motivo; contabilización es de una sola vez
  (segunda llamada levanta error); no se puede eliminar un viaje fuera de
  borrador.
- `test_passenger_event.py`: un evento de subida se proyecta a la línea de
  pasajero; una `idempotency_key` duplicada del mismo dispositivo es
  rechazada por la base (constraint real, no sólo a nivel de aplicación);
  anular un evento borra la línea proyectada.
- `test_contract.py`: no se puede aprobar un contrato con plantilla sin
  validar; la instantánea de tarifas se congela una vez y no cambia si la
  tarifa vigente cambia después; las variables `{{ }}` del cuerpo del
  contrato se sustituyen correctamente.
- `test_security.py`: un usuario sin el grupo de costeo no puede costear;
  el flujo de emparejamiento de dispositivo (código → token) funciona;
  un token de un dispositivo revocado deja de autenticar.

## 5. No ejecutado / no cubierto en esta entrega

- **API móvil por HTTP** (`/mobilization/v1/*`): el código de los
  controladores existe y sigue el mismo contrato que los tests de
  `step.mobilization.driver.device`/`passenger.event` ya prueban a nivel
  ORM, pero no se hicieron pruebas HTTP de extremo a extremo (`curl`/cliente
  real) contra un servidor corriendo, ni pruebas de la sección 8.3 completa
  del encargo (offline, reintentos, reloj incorrecto, dos dispositivos
  compitiendo, batería). Requeriría un cliente/PWA real, fuera del alcance
  de esta entrega (ver decisión en `02_ARQUITECTURA_Y_DECISIONES.md §6`).
- **`step_mobilization_agriculture`**: sólo validación estática (ver
  limitación de Enterprise arriba). Su lógica (`_get_cost_distribution_hook`,
  fundo `ondelete=restrict`) no tiene tests automatizados propios en esta
  entrega.
- **Reporte de datos antes/después** (Fase 1.2 / entregable #5): no
  ejecutable porque no hay acceso a ninguna base real de Odoo desde este
  entorno (ver limitación documentada en `02_ARQUITECTURA_Y_DECISIONES.md
  §0`). El script de auditoría queda como plantilla, no como resultado.
- **Migración real** (`pre-migrate.py` de step_hr): su lógica se revisó
  manualmente y es SQL directo y acotado, pero no se ejecutó contra una base
  con datos históricos reales de `step.movi.registry`/`hr.route` (no existe
  tal base accesible aquí) — sólo se probó el camino de instalación limpia
  (sin datos previos que migrar).
