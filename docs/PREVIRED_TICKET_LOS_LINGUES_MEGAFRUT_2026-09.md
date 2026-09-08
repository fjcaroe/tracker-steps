# Ticket PreviRed — Los Lingues y Megafrut (nómina agosto 2026)

**Módulo:** `step_hr_previred` · **De:** `18.0.3.4.0` → **A:** `18.0.3.5.0`
**Fecha:** 2026-09-04 · **Base:** `SyS` (producción, `odoo18-sys`, puerto 8070)
**Origen:** `Ticket imposiciones Los Lingues.docx`, `Ticket PreviRed Megafrut.docx`

## 1. Errores reportados

### Agrícola Los Lingues (4 errores + 6 advertencias)

| Línea | RUT | Error | Enviado | Esperado |
|---|---|---|---|---|
| 1 | 20681876-K | Error de formato en Centro de Costos | `AdministraciÃ³n` | — |
| 5 | 14250811-7 | Renta imponible MUTUAL no informada | `0.0` | `0.0` |
| 5 | 14250811-7 | Cotización SIS (campo 29) no corresponde a la tasa 1.78% | `12.637` | `11.993` |
| 5 | 14250811-7 | Cotización Expectativa de Vida (campo 94) incorrecta | `4.947` | `4.851` |

Advertencia adicional relevante (no genérica de centro de costo):
`14250811-7`, línea 5: «Cotización Accidente del Trabajo Mutual inválida» —
enviado `206`, esperado `0`.

### Megafrut Limitada (3 errores)

Los tres son el mismo error de formato en Centro de Costos
(`AdministraciÃ³n`), en los RUT 09800422-K, 07016555-4 y 14692801-3.

## 2. Corregido en `18.0.3.5.0`

**Campo 105 «Centro de Costos, Sucursal, Agencia».** `previred_extractor.py`
tomaba `cost_center.code or cost_center.name` y lo escribía tal cual. Un
nombre con tilde («Administración») se codifica en UTF-8 al escribir el TXT;
Previred lo relee como Latin-1 y muestra «AdministraciÃ³n» — el patrón
clásico de doble codificación (`ó` = `0xC3 0xB3` en UTF-8, que en Latin-1 son
los caracteres «Ã³»). El resto del módulo ya translitera nombres a ASCII con
`previred.strip_accents` (ver el comentario de diseño en
`tools/previred.py` sobre por qué UTF-8 y Latin-1 deben coincidir byte a
byte); al campo 105 no se le aplicaba. Se agregó esa transliteración antes de
truncar a 20 caracteres.

Esto resuelve el 100 % de los errores de Megafrut (3/3) y uno de los cuatro
de Los Lingues (RUT 20681876-K). Prueba de regresión:
`test_v98_cost_center_strips_accents` en
`step_hr_previred/tests/test_dataset.py`.

## 3. NO corregido en este corte — RUT 14250811-7 (Marcelo Soto)

Los otros tres hallazgos de Los Lingues (SIS, Expectativa de Vida, Renta
Imponible/Cotización Mutual) **no** son un defecto de formato del TXT: son un
cálculo de nómina. `step_hr_previred` es, por diseño, una capa de exportación
que **no recalcula importes** («ninguna salida vuelve a consultar la base ni
recalcula un importe», ver cabecera de `previred_extractor.py`); los campos
27 (Renta Imponible AFP), 29 (SIS) y 98 (Cotización Mutual) los computa el
motor de nómina del proveedor (`l10n_cl_hr`, Blueminds) mediante reglas
salariales que no están en este repositorio.

### Lo que dice el ticket

Cuando un trabajador tiene licencia médica todo el mes (30 días), la renta
imponible para las cotizaciones de cargo del empleador es la Renta Imponible
del Mes Anterior a la Licencia — **RIMA**, campo 92 — en vez del imponible
normal del mes (que sería 0, al no haber días trabajados). Para
RUT 14250811-7: RIMA = **$673.750**.

### Verificación numérica

| Campo | Fórmula supuesta | Cálculo | Resultado | Esperado por PreviRed | ¿Coincide? |
|---|---|---|---|---|---|
| 29 SIS | RIMA × 1,78 % | 673.750 × 0,0178 = 11.992,75 | **11.993** | 11.993 | ✅ exacto |
| 94 Expectativa de Vida | RIMA × tasa vigente (`life_expectancy_rate`, hoy 1,00 % desde 2026-08) | 673.750 × 0,01 = 6.737,50 | 6.738 | 4.851 | ❌ no coincide |
| 98 Mutual | 0 tras 30 días de licencia acumulada | — | 0 | 0 | ✅ (regla clara, no implementada) |
| 97 Renta Imp. Mutual | — | — | — | 0 (hoy se envía vacío/«no informada», no `0`) | ⚠️ pendiente |

**SIS cuadra exactamente con RIMA × 1,78 %.** Esto confirma la regla del
ticket para ese campo específico y que 1,78 % es la tasa SIS vigente del
período (el propio mensaje de error de PreviRed la nombra).

**Expectativa de Vida no cuadra** con la misma base (RIMA) y la tasa que hoy
tiene el código (1,00 % desde agosto 2026, en
`previred.life_expectancy_rate`). La diferencia no es de redondeo: da 6.738
en vez de 4.851. Dos explicaciones posibles, ninguna verificable desde este
repositorio:

1. La tasa vigente para Expectativa de Vida en agosto 2026 no es 1,00 % (el
   valor codificado podría estar desactualizado), o
2. El campo 94 no es un porcentaje plano de la renta imponible: «Expectativa
   de Vida» sugiere una tabla actuarial por edad/sexo, no una tasa única —
   en cuyo caso ningún cálculo `base × tasa` va a coincidir sin esa tabla.

**Mutual (campo 98) tiene una regla clara pero no implementada**: según la
guía embebida en el ticket, la cotización de accidente del trabajo es de
cargo del empleador sólo durante los **primeros 30 días** de una licencia;
después, la responsabilidad pasa a la Isapre/AFC. Este trabajador acumula 60
días de licencia, así que corresponde 0. Implementar esto requiere calcular
cuántos días de licencia **continua** lleva el trabajador contando también
liquidaciones anteriores (una licencia puede empezar en un mes y seguir en el
siguiente) — es una ventana temporal, no un dato de la liquidación del mes en
curso.

### Por qué no se implementó a ciegas

Estos tres campos mueven dinero de cotizaciones previsionales reales,
declarado a un organismo del Estado, para clientes en producción. Antes de
tocarlos se necesita:

1. **RIMA real**: confirmar que se calcula como «renta imponible AFP de la
   última liquidación válida antes de que comenzara la licencia» (el bridge
   SimpleDigital ya tiene un método análogo,
   `_calculate_renta_imponible_last_month`, que se podría adaptar para
   Blueminds) — y no, por ejemplo, la liquidación inmediatamente anterior sin
   más (podría ser otro mes con licencia parcial y no reflejar el sueldo
   real).
2. **Tasa/tabla de Expectativa de Vida** vigente para el período 2026-08,
   con su fuente oficial — para confirmar o corregir
   `previred.life_expectancy_rate`.
3. **Regla exacta de los 30 días de licencia** para el aporte Mutual:
   ¿continuos dentro de la misma incapacidad (mismo diagnóstico/reposo), o
   acumulados en el año? ¿Se cuentan días corridos o hábiles?
4. Confirmar si esta corrección **sólo** aplica cuando el campo 13 (Días
   Trabajados) es 0 por licencia todo el mes, o también a licencias
   parciales dentro del mes (en cuyo caso el imponible sería «imponible del
   mes trabajado + RIMA proporcional», bastante más complejo).

Con esas cuatro confirmaciones, la corrección es acotada: extender
`_set_worked_days`/`_set_life_expectancy` (o un método nuevo) en
`previred_extractor.py`, con el mismo patrón de código auditable y hallazgos
trazables que ya usan los campos 13 y 94 (fallback), y sus pruebas.

## 4. Verificación

- `py_compile` de los archivos tocados: OK.
- Parseo de los 5 XML del módulo: OK.
- `git diff --check`: OK (sólo avisos LF/CRLF).
- Suite `--test-tags=/step_hr_previred` (105 pruebas) en un clon desechable de
  `LAB_TAREAS` (`PRV_FIX_UPG`), con el código parcheado superpuesto **antes**
  de `/opt/rrhh` y `/opt/dev_odoo18/odoo_agriculture` en el `addons-path` —
  ningún árbol real (`/opt/dev_odoo18`, `/opt/luis_odoo18` = `SyS`,
  `/opt/demo_odoo18`) fue modificado:

  | Prueba | Resultado |
  |---|---|
  | `test_v98_cost_center_strips_accents` (nueva, este ticket) | ✅ pasa |
  | `test_v98_cost_center_uses_code_or_name_from_contract` (regresión) | ✅ pasa |
  | Resto de la suite (103 pruebas) | ✅ pasan |
  | `TestMultiplesContratos.test_same_rut_in_two_companies_is_validated_separately` | ❌ error preexistente, **no relacionado** |

  El único error (`0 failed, 1 error(s) of 105 tests`) es
  `odoo.exceptions.UserError: El Rut debe ser único`, lanzado por
  `l10n_cl_hr/model/hr_employee.py:79` (`_rut_unique`) al crear un segundo
  empleado con el mismo RUT en otra compañía — el motor de nómina vendor
  instalado en este clon de `LAB_TAREAS` valida el RUT de forma global, no
  por compañía, rompiendo un supuesto de esa prueba (`test_correcciones2.py`,
  ajena a `previred_extractor.py` y a este ticket). Confirmado por traza
  completa: no pasa por ningún archivo tocado en esta corrección. Documentado
  aquí en vez de descartado en silencio.
- No se tocó `SyS` (producción, Los Lingues y Megafrut), `LAB_TAREAS`,
  `STEPS_DEMO` ni `STEPS_DEMO_SYS`. Base y artefactos desechables
  (`PRV_FIX_UPG`, `/tmp/previred_fix_addons`, `data-dir` temporal, tar y
  script) eliminados al terminar; log de evidencia conservado en
  `odoo-new:/tmp/previred_fix_upg_20260904_203438.log`.

## 5. Despliegue a `SyS` (producción) — 2026-09-04

Autorizado explícitamente por el usuario. Procedimiento (backup → copia
quirúrgica de los 4 archivos tocados → upgrade offline → reinicio →
verificación, con rollback automático si algo fallaba):

1. **Backup previo**: `pg_dump -Fc` de `SyS` (22.720.253 B) + copia de los 4
   archivos previos del módulo, en
   `/opt/backups/previred_ticket_lingues_megafrut_20260904T214336Z/`
   (conservado).
2. **Despliegue**: sólo `__manifest__.py`, `CHANGELOG.md`,
   `models/previred_extractor.py` y `tests/test_dataset.py` sobre
   `/opt/luis_odoo18/odoo_agriculture/step_hr_previred/` — ningún otro
   archivo del árbol de producción se tocó.
3. **Servicio detenido**, `odoo-bin -u step_hr_previred --stop-after-init`
   → **RC 0**, sin `ERROR`/`CRITICAL`/`Traceback` en el log (326 módulos
   cargados, registro reconstruido en 17,2 s).
4. **Servicio reiniciado**: `active (running)`, memoria y tareas normales.
5. **Verificación**: `ir_module_module` confirma
   `step_hr_previred | 18.0.3.5.0 | installed`; `GET /web/login` → **HTTP
   200**; el archivo desplegado contiene `strip_accents` en el campo 105.

Log de la migración conservado en
`odoo-new:/tmp/previred_deploy_sys_20260904T214336Z.log`. No se tocó
`LAB_TAREAS`, `STEPS_DEMO` ni `STEPS_DEMO_SYS`.

Los Lingues y Megafrut ya pueden regenerar y volver a subir el TXT de agosto
2026: el error de Centro de Costos (4 de los 7 hallazgos) queda resuelto.

## 6. Siguiente paso

1. Confirmar con el dueño funcional/Contabilidad los cuatro puntos de la
   sección 3 (RIMA, tasa de Expectativa de Vida, regla de los 30 días para
   Mutual, alcance de licencias parciales).
2. Con eso, un corte 2 de este ticket que implemente RIMA + SIS + Expectativa
   + tope de 30 días para Mutual, con pruebas para el caso exacto de
   RUT 14250811-7, y su propio despliegue a `SyS`.
