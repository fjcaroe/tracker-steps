# Corte vertical — Carencia y reingreso por cuartel

Módulo: **`step_agro_traceability`** (Steps - Trazabilidad Fitosanitaria)
Fecha: **2026-08-21** · Rama: `codex/web-tracker-redesign`
Estado: desplegado y validado en **Desarrollo** y **Demo**

---

## 1. Problema que resuelve

El dato fitosanitario ya se capturaba completo y **nadie lo usaba**
(ver [auditoría §4.1](AUDITORIA_PRODUCTO_AGRICOLA.md)):

- `product.template.dia_carencia` / `.hrs_reingreso` existían desde `step_hr`
  y solo se pintaban en un formulario.
- `x_aplicacion_foliar` registraba producto, cuartel, fecha y las cuatro
  carencias (etiqueta / mayor / UE / USA).
- `step.cosecha.registry` registraba cuartel y fecha de cosecha.
- **Nada cruzaba esos dos hechos.**

El sistema no podía responder *«¿puedo cosechar este cuartel hoy?»* ni
*«¿puede entrar personal sin EPP?»*, pese a que ambas son obligaciones
explícitas del SAG (carencia y período de reingreso, definidos por la etiqueta
del plaguicida).

## 2. Qué hace ahora

1. **Deriva** de cada aplicación fitosanitaria una *restricción por cuartel*
   con la fecha mínima de cosecha y la hora de reingreso seguro.
2. **Muestra** el estado fitosanitario en el registro de cosecha: badge
   (`Liberado` / `En carencia` / `Sin cuartel`), fecha permitida y banner rojo
   con el detalle y un enlace a las aplicaciones que lo explican.
3. **Advierte o bloquea** la aprobación de una cosecha dentro de carencia,
   según política por empresa.
4. **Entrega un tablero** filtrable y agrupable de restricciones vigentes por
   fundo, cuartel y centro de costo, con vista pivote.

## 3. Diseño

### 3.1 Por qué un modelo nativo y no una extensión de Studio

`x_aplicacion_foliar` es un modelo *manual* (Studio, vive en la base). Un módulo
Python **no puede** declarar `_inherit` sobre un modelo manual: cuando se cargan
las clases Python el modelo aún no está en el registro y la carga falla. Por eso:

- El módulo **lee** `x_aplicacion_foliar` en tiempo de ejecución, con guardas
  (`self.env.get(...)`, `campo in _fields`), y degrada a vacío si Studio cambia.
- **Materializa** el resultado en `step.phyto.restriction`, un modelo nativo,
  versionado, con ACL, regla multiempresa e índices.

### 3.2 Descubrimiento por capacidad, no por nombre

Los sufijos que Studio genera (`x_aplicacion_foliar_line_6808a`) no están
garantizados entre bases. `_discover_line_models()` recorre los `one2many` de la
aplicación y elige:

- la línea que tiene `x_studio_producto` → productos aplicados;
- la línea que tiene `x_studio_cuartel` → cuarteles intervenidos.

### 3.3 Frescura del dato: dos caminos deliberados

| Camino | Se usa en | Garantía |
|---|---|---|
| Tabla materializada | banner del formulario, listas, pivote, tablero | rápida; se refresca por cron horario y por el botón «Recalcular desde BPA» |
| Lectura **en vivo** del origen | `action_apro()` | una aplicación cargada hace un minuto **siempre** pesa en la decisión de aprobar |

El control que importa (bloquear/advertir) nunca depende de la caché.

### 3.4 Criterio de carencia configurable

`res.company.step_phyto_criterion`: etiqueta (SAG) · **la mayor de todas
(por defecto)** · UE · USA.

La etiqueta es la exigencia legal chilena; los mercados de destino suelen ser
más restrictivos, y el maestro de productos ya trae los cuatro valores. El valor
por defecto es el más conservador. Además, **si el criterio de destino elegido
no tiene días cargados, se cae al valor de etiqueta** — un mercado sin dato no
puede relajar el control legal.

### 3.5 Política configurable

`res.company.step_phyto_policy`: desactivado · **advertir (por defecto)** ·
bloquear.

El valor por defecto es `advertir` para no romper ningún flujo existente al
instalar. Activar el bloqueo duro es un cambio de una lista desplegable en
**Ajustes → Compañías → (empresa) → Trazabilidad fitosanitaria**.

El reingreso **advierte siempre, nunca bloquea**: cosechar dentro del período de
reingreso es legal usando EPP; lo que no es legal es entrar sin él. El aviso
queda en el historial del registro.

## 4. Archivos

### Nuevos — `step_agro_traceability/`

```
__manifest__.py                         depende de step_hr, step_cosecha,
                                        step_bpa_irrigation, step_agricultural_access
hooks.py                                respaldo inicial idempotente al instalar
models/phyto_restriction.py             modelo + motor de lectura y materialización
models/res_company.py                   política y criterio
models/step_cosecha_registry.py         estado fitosanitario + guardia en action_apro
security/ir.model.access.csv            lectura para Cosecha y BPA; escritura solo BPA
security/phyto_security.xml             regla global multiempresa
data/ir_cron.xml                        recálculo horario
views/phyto_restriction_views.xml       list, form, search, pivot, acciones
views/step_cosecha_registry_views.xml   banner + badge + columna de lista
views/res_company_views.xml             configuración
views/menu_views.xml                    menús en BPA y en Cosecha
static/src/scss/phyto.scss              estilo del banner
tests/test_phyto_restriction.py         16 pruebas
```

### Modificados

| Archivo | Cambio |
|---|---|
| `step_cosecha/models/step_cosecha_registry.py` | **Corrección:** agrega `from odoo.exceptions import UserError`. El archivo usaba `UserError` en 26 puntos sin importarlo; cada validación de negocio reventaba con `NameError` y mostraba «Ocurrió un error» genérico en vez del mensaje. |
| `step_cosecha/__manifest__.py` | versión `18.0.1.5.1` → `18.0.1.5.2` |

> **Nota sobre `step_bpa_irrigation`.** Durante la auditoría se propuso declarar
> `studio_customization` como dependencia (§4.2). **La propuesta era incorrecta
> y se descartó**: `studio_customization` no tiene directorio en disco (vive solo
> en la base), de modo que como dependencia de manifiesto queda «no satisfecha»
> y deja el módulo sin cargar. Las referencias a sus XML IDs se resuelven en
> tiempo de ejecución vía `ir.model.data` sin necesidad de la dependencia. El
> manifiesto quedó como estaba.

## 5. Pruebas

`step_agro_traceability/tests/test_phyto_restriction.py` — **16 pruebas,
0 fallos, 0 errores** en `LAB_TAREAS`.

```bash
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin -c /etc/dev_odoo18.conf -d LAB_TAREAS -u step_agro_traceability --test-enable --test-tags step_phyto --stop-after-init --http-port=8899 --gevent-port=8898
```

Cubren: cálculo de ventanas, expiración, reingreso aislado, evaluación por
fecha de cosecha, las tres políticas, cosecha sin cuartel, cosecha fuera de
carencia con bloqueo activo, idempotencia del refresco, criterio conservador,
caída a etiqueta cuando falta el dato de destino, HTML del historial, y la
regresión del `UserError` de `step_cosecha`.

Las pruebas **no dependen de Studio**: construyen las restricciones
directamente, que es exactamente lo que el motor produce.

## 6. Validación en navegador (Desarrollo)

Con datos reales de `LAB_TAREAS`:

1. Menú **BPA y Riego → BPA → Carencia y reingreso** presente y operativo.
2. **3 restricciones** derivadas automáticamente de las 4 aplicaciones
   existentes al instalar (la cuarta no tenía cuartel: se omite correctamente).
   El criterio «la mayor» tomó 9 días de glifosato en vez de los 7 de etiqueta.
3. Registro de cosecha `OC00001` (cuartel C01, 17-02-2026): badge verde
   **Liberado** — correcto, la carencia vencía el 11-02-2026.
4. Se registró en BPA la aplicación **BPA202600003** (hoy, cuartel C01 Crunch 18,
   producto *2,4-D 480*: carencia 5 días, reingreso 12 h).
5. Tras «Recalcular desde BPA», el tablero muestra la fila roja
   **En carencia · cosecha permitida desde 26/08/2026 08:00 · faltan 5 días**.
6. Al elegir ese cuartel en un registro de cosecha nuevo, aparece de inmediato
   el banner rojo *«Cuartel en carencia hasta el 2026-08-26 por 1 aplicación(es):
   2,4-D 480»* con enlace **Ver aplicaciones**.
7. Con política **Advertir**: aprueba y deja la alerta en el historial.
8. Con política **Bloquear**: diálogo **«Operación no válida»** con el motivo y
   la instrucción; el registro permanece en *Ingresado*.
9. Sin tracebacks nuevos en `journalctl -u odoo18-dev.service`.
10. `https://desarrollo.stepsapp.cl/web/login` → **200**.

La política de la empresa quedó restituida a su valor por defecto (**Advertir**).

### Datos de prueba dejados en Desarrollo

- Aplicación foliar `BPA202600003` (21-08-2026).
- Registro de cosecha `OP00008-Prueba carencia C01`.

Se dejan a propósito para que el flujo sea reproducible; se pueden archivar sin
efecto sobre nada más. **Demo no recibió ningún dato de prueba.**

## 7. Validación en Demo

| Comprobación | Resultado |
|---|---|
| `step_agro_traceability` | `installed` 18.0.1.0.0 |
| `step_cosecha` | 18.0.1.5.2 (con la corrección) |
| `https://demo.stepsapp.cl/web/login` | **200** |
| Base neutralizada | `False` |
| Proveedor DTE | `SIIDEMO` |
| SMTP | 1 servidor activo (no se envió correo) |
| Cron de cola de correo | activo |
| Cron fitosanitario | activo, cada 1 hora |
| `step_qa`, `l10n_cl_edi`, `l10n_cl_edi_stock`, `l10n_cl_edi_factoring` | `installed` |
| Restricciones / cosechas | 0 / 0 — base limpia |
| Estado vacío | *«Aún no hay restricciones vigentes»* con explicación de cómo se poblará |
| Tracebacks nuevos | ninguno |

## 8. Respaldos

Todos con `pg_dump -Fc`.

| Base | Archivo | SHA-256 |
|---|---|---|
| `LAB_TAREAS` antes | `/opt/fernando_odoo18/backups/phyto-carencia-20260821/LAB_TAREAS-before.dump` | `db9fe2e87580e283e22f549d1aa63b3832f14ce4343a3efbf4b8c8b5741b284d` |
| `LAB_TAREAS` después | `/opt/fernando_odoo18/backups/phyto-carencia-20260821/LAB_TAREAS-after.dump` | `0f4a3391e761aa0c7d92333d38f7f62fa210bbe71e6406ffe8136c9e351e0d0d` |
| `STEPS_DEMO` antes | `/opt/demo_odoo18/backups/phyto-carencia-20260821/STEPS_DEMO-before.dump` | `3510628cf4f3a16cbdd101bc6980a661493c309214053327357a102dd0a11af3` |
| `STEPS_DEMO` después | `/opt/demo_odoo18/backups/phyto-carencia-20260821/STEPS_DEMO-after.dump` | `e8ceb5b4bd263abba34ed00d1ad45b68e6f2d1bf2ad32a1fe3941c8c04f01aef` |

## 9. Dónde revisarlo

| Qué | URL |
|---|---|
| Tablero de carencia (Desarrollo) | `https://desarrollo.stepsapp.cl/odoo/action-step_agro_traceability.action_step_phyto_restriction` |
| Historial por cuartel (Desarrollo) | `https://desarrollo.stepsapp.cl/odoo/action-step_agro_traceability.action_step_phyto_restriction_all` |
| Registro de cosecha con banner | `https://desarrollo.stepsapp.cl/odoo/action-1361/20` |
| Tablero de carencia (Demo) | `https://demo.stepsapp.cl/odoo/action-step_agro_traceability.action_step_phyto_restriction` |
| Configuración | Ajustes → Compañías → (empresa) → **Trazabilidad fitosanitaria** |

Menús: **BPA y Riego → BPA → Carencia y reingreso**, **BPA y Riego → Informes →
Historial fitosanitario por cuartel**, **Cosecha → Planificar Cosecha → Carencia
por cuartel**.

## 10. Riesgos y límites conocidos

1. **Acoplamiento a Studio.** Si se renombran o eliminan
   `x_aplicacion_foliar` o sus campos `x_studio_producto` / `x_studio_cuartel`,
   el motor deja de encontrar datos y devuelve vacío — **sin romper la
   instalación**, pero también sin avisar. Mitigación real: migrar la aplicación
   foliar a un modelo nativo (siguiente corte propuesto).
2. **Cobertura del dato.** Hoy solo **2 de 1480** productos tienen días de
   carencia cargados (`2,4-D 480` y `GLIFOSATO 48 % SL`). El control es tan
   bueno como el maestro: hay que completar `dia_carencia` y `hrs_reingreso` en
   los productos fitosanitarios reales. Un producto sin carencia cargada no
   genera restricción y la cosecha pasa sin alerta.
3. **Aplicaciones sin cuartel** no generan restricción (no hay dónde aplicarla).
   Conviene volver obligatorio el cuartel en la línea de maquinaria de BPA.
4. **El botón «Recalcular desde BPA»** exige seleccionar al menos una fila
   (limitación de los botones de cabecera en vistas lista de Odoo 18). La
   frescura real está garantizada por el cron horario y por la verificación en
   vivo al aprobar.
5. `step.cuartel.line` sigue **sin `company_id`**; la regla multiempresa de la
   restricción se apoya en su propio `company_id`, tomado de la aplicación.

## 11. Siguientes pasos propuestos

En orden de valor sobre riesgo:

1. **Cuaderno de campo SAG** generado desde las aplicaciones y las restricciones
   ya calculadas (`x_cuaderno_de_campo` existe y tiene 0 registros).
2. **Carga del maestro fitosanitario**: completar carencia y reingreso de los
   productos reales, y validar `x_studio_vencimiento_autorizacin` para alertar
   sobre productos con autorización SAG vencida.
3. **Migrar `x_aplicacion_foliar` a modelo nativo**, empezando por los campos
   que sostienen reglas (fecha, cuartel, producto, dosis).
4. **Corregir el costeo de tarjas propias** (auditoría §4.3 y §4.4). Alto valor,
   pero exige decisión del usuario sobre cómo migrar los registros históricos ya
   contabilizados. **No ejecutado en esta entrega.**
