# Tesorería — Correcciones 1 (30-08-2026)

Identidad de la aplicación y semanas calendario reales en el flujo de caja.

`step_account_treasury 18.0.1.1.1` → **`18.0.1.2.0`**.

## 1. Lo pedido

1. El módulo decía «Facturando»; debe decir «Tesorería», con logo en el estilo Steps.
2. Las columnas W1..W5 del formulario de flujo deben mostrar la semana
   calendario real del horizonte (W35, W36, … W39).

## 2. Cambios

| Archivo | Cambio |
|---|---|
| `views/treasury_menus.xml` | `menu_treasury_root` pasa a raíz con `web_icon`; nuevo `menu_treasury_from_accounting` como atajo dentro de `account.menu_finance` |
| `__manifest__.py` | `application: True`, versión, nuevo asset JS |
| `static/description/icon.png` | Icono nuevo, 1254×1254, paleta y encuadre de los demás iconos Steps |
| `models/cashflow.py` | `_bucket_labels()` y `_bucket_label_hints()` |
| `models/cashflow_line.py` | `bucket_label` (Char, store, compute agrupado por flujo) |
| `models/cashflow_summary.py` | Resumen HTML, `_export_matrix`, columna «Semana» del XLSX y payload del tablero usan las etiquetas dinámicas |
| `report/treasury_report.xml` | Cabecera del PDF con la semana y su rango de fechas |
| `static/src/js/treasury_week_columns.js` | Widget `treasury_week_lines`: reetiqueta las columnas `amount_w1..w5` de las siete hojas desde el `start_date` del flujo |
| `views/cashflow_views.xml` | Las siete hojas usan el widget; `bucket_label` como columna opcional, campo de búsqueda y agrupador |
| `static/src/scss/treasury.scss` | Estilo del subtítulo con el rango de fechas |

### Por qué un widget de cliente y no `fields_get`

El encabezado de una lista sale de `column.label`, que el cliente arma desde
`props.archInfo.columns`. Reetiquetar por contexto en `fields_get` no sirve:
la subvista se resuelve en el `get_views` del padre, antes de que exista el
registro, así que no hay `start_date` que leer. `TreasuryWeekLinesField`
extiende `X2ManyField` y reescribe `rendererProps.archInfo.columns` con el
`start_date` del registro padre; `processAllColumn` corre en cada render, de
modo que mover el horizonte re-rotula solo.

El cálculo de semana ISO del JS se contrastó contra `date.isocalendar()[1]` de
Python en los bordes de año (W53, W1): coinciden.

## 3. Pruebas

`60 tests, 0 failed, 0 error(s)` sobre base desechable `TES_TEST_20260829`
(creada e instalada desde cero, eliminada al terminar). Seis pruebas nuevas y
una actualizada:

- `test_bucket_labels_use_the_real_calendar_week`
- `test_bucket_labels_align_with_iso_weeks_when_starting_on_monday`
- `test_bucket_labels_fall_back_without_start_date`
- `test_line_carries_the_calendar_week`
- `test_summary_header_shows_the_calendar_week`
- `test_treasury_is_its_own_application`
- `test_menu_and_actions_are_installed` — actualizada: la raíz ya no cuelga de
  `account.menu_finance`; el que cuelga ahí es el atajo.

Verificación manual en navegador sobre la base desechable: baldosa y barra de
la app, columnas de las siete hojas (W35…W39), pestaña Resumen con el rango de
fechas, y contenido del PDF y del XLSX.

## 4. Despliegue

| Ambiente | Base | Versión | Servicio | HTTP |
|---|---|---|---|---|
| Demo | `STEPS_DEMO` | 18.0.1.2.0 | `odoo18-demo.service` activo | 200 |
| Desarrollo | `LAB_TAREAS` | 18.0.1.2.0 | `odoo18-dev.service` activo | 200 |
| Producción | `karo_consultorias` | — | sin tocar | — |

Tesorería no está instalada en Producción. Respaldo previo:
`/opt/fernando_odoo18/backups/tesoreria-correcciones1-20260830-005827`.

`FC20260001` (Desarrollo, inicio 29/08/2026) muestra W35…W39.

## 5. Pendiente

1. **Icono vectorial, no render 3D.** Los otros iconos Steps son
   ilustraciones 3D; este comparte paleta, encuadre y el motivo del engranaje
   pero es plano con volumen. Reemplazar el PNG basta si se quiere el render.
2. **`action_cashflow_line_graph` sigue agrupando por `bucket`.** Agrupar por
   `bucket_label` ordenaría el eje alfabéticamente (`Otros, Vencido, W35…`),
   rompiendo el orden del horizonte. Se dejó el agrupador «Semana calendario»
   disponible en la vista de búsqueda.
3. **Horizonte que cruza el cambio de año.** Mostraría `W52, W53, W1…`. El
   resumen y el PDF llevan el rango de fechas; las hojas no. Si aparece el
   caso, agregar el año al rótulo.
4. **Demo no tiene flujos de caja cargados.**

## 6. Recomendaciones

- Iniciar el horizonte en lunes: es lo único que hace que la ventana de siete
  días y la semana ISO sean la misma.
- Cargar un flujo de ejemplo en Demo.
- Revisar la membresía de `group_treasury_reader`: ahora la app es visible como
  baldosa (2 usuarios en Demo, 6 en Desarrollo).
