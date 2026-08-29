# Apps duplicadas en el menú principal (29-08-2026)

Diagnóstico y corrección de las aplicaciones que aparecían dos veces en el
front de Desarrollo y Demo.

## 1. Diagnóstico

Cinco apps duplicadas, idénticas en ambos ambientes, con **dos causas
distintas**.

### Causa A — menús raíz de Studio que quedaron activos (4 apps)

Las apps se prototiparon en Studio y luego se reescribieron como módulos
Python. Al instalar el módulo se creó un segundo menú raíz con el mismo nombre
e icono, pero el original de Studio nunca se archivó.

| App | Menú del módulo | Menú de Studio |
|---|---|---|
| BPA y Riego | `step_bpa_irrigation.menu_bpa_root` | `studio_customization.bpa_y_riego_3e945603…` |
| Fletes | `step_operations_ui.fletes_7a210622…` | `studio_customization.fletes_7a210622…` |
| Protección Laboral | `step_labor_protection.menu_labor_root` | `studio_customization.proteccion_laboral_d71afde5…` |
| QA-Inspecciones | `step_qa.menu_step_qa_root` | `studio_customization.qa_inspecciones_791dce79…` |

Los menús de Studio **no eran copias vacías**: contenían maestros e informes
que el menú nuevo todavía no replicaba, apuntando a datos en uso
(`x_sustancia_activa` 659 registros, `x_aptitud_plaguicidas` 63, entrega de
EPP, órdenes de flete, riesgos laborales…). Archivarlos sin más habría
escondido esa funcionalidad.

También tenían un efecto lateral de permisos: la raíz de Studio no llevaba
grupos, así que la app se veía sin restricción, mientras que la del módulo sí
está acotada por `step_agricultural_access`.

### Causa B — Steps Tracker: el mismo menú declarado en dos módulos

`step_hr/views/step_tracker_sync_views.xml` declaraba el árbol completo del
Tracker y `step_tracker_odoo` lo volvía a declarar. Ambos exponían los mismos
modelos `step.tracker.*` con la misma estructura, así que sobraba uno.

### No es duplicado

`Gestión y Costos` vs `Gestión y Costos borrador`: mismo patrón, pero el
equipo ya lo resolvió renombrando el de Studio. Se dejó como está.

## 2. Solución aplicada

Decisión del usuario: **migrar los submenús y luego archivar** los menús de
Studio, y **quitar el menú del Tracker de `step_hr`**.

### Fusión de menús

`step_agricultural_access` incorpora `ir.ui.menu._consolidate_duplicated_apps()`:

1. Empareja cada raíz de Studio con la raíz del módulo del mismo nombre.
2. Recorre el árbol de Studio: lo que no existe en el módulo se **mueve**; lo
   que existe se funde recursivamente; lo redundante se **archiva**.
3. Pasada final por app: archiva entradas repetidas en distinto nivel sólo
   cuando **coinciden modelo y nombre** (si el nombre difiere puede ser otra
   vista, y no se toca).
4. Archiva la raíz de Studio ya vacía.

Nada se borra: todo es `active = False` o cambio de `parent_id`, reversible.

Se ejecuta desde tres puntos: `post_init_hook` (instalación limpia), migración
`18.0.2.2.1` (bases existentes) y las pruebas.

### Steps Tracker

- `step_hr/views/step_tracker_sync_views.xml`: se retiró el bloque de menús
  (19 `menuitem` + 1 `record`). Los modelos, vistas y acciones quedan intactos.
- `step_agricultural_access/views/agricultural_menu_security.xml`: los 6
  registros de permisos del Tracker apuntan ahora a `step_tracker_odoo.*`, y el
  módulo declara la dependencia.
- `step_operations_ui/views/app_icons.xml`: se eliminó el registro que fijaba
  el icono sobre el menú retirado; `step_tracker_odoo` ya declara el suyo con
  el mismo archivo (sha256 `1631805f…`).

## 3. Error cometido y cómo se corrigió

La primera versión comparaba los nombres de menú **en el idioma de la sesión de
la migración (`en_US`)**, mientras los menús se mantienen en `es_CL`. Con
nombres distintos entre idiomas emparejaba ramas equivocadas.

- Se revirtió en Desarrollo desde el respaldo tomado minutos antes,
  restaurando `parent_id` y `active` de los 25 menús afectados y verificando
  0 diferencias contra el dump.
- Se corrigió: ahora se comparan **todas las traducciones** y basta con que una
  coincida (`_label_variants`). Hay una prueba de regresión específica
  (`test_matching_uses_every_translation`).
- Se validó con un **ensayo sobre datos reales en transacción con rollback**
  antes de volver a aplicar.

Aclaración: mi primera lectura del árbol resultante venía de una consulta SQL
mal ordenada (agrupaba por nivel, no por padre) y exageró el daño. El error de
idioma era real igualmente; la corrección además mejoró el resultado (9
entradas redundantes eliminadas frente a 2).

## 4. Resultado

Ejecución real de la migración (idéntica en ambos ambientes):

```
pares: BPA y Riego, QA-Inspecciones, Protección Laboral, Fletes
menús movidos: 20
redundantes archivados: 9
raíces archivadas: 4
apps en el menú principal: 53 -> 49 (Desarrollo)
```

Verificación con la sesión real del usuario, contra el endpoint que alimenta el
selector de aplicaciones (`/web/webclient/load_menus`):

| | Apps | Duplicadas |
|---|---|---|
| https://desarrollo.stepsapp.cl | 47 | **ninguna** |
| https://demo.stepsapp.cl | 46 | **ninguna** |

`Steps Tracker` queda una sola vez, publicado por `step_tracker_odoo` y con su
grupo de permisos asignado.

## 5. Versiones y huellas

| Módulo | Versión | SHA-256 (local = Desarrollo = Demo) |
|---|---|---|
| `step_hr` | 18.0.1.4.0 | `c33d17b5d338853b11f3a1a11d4f02d2e35f6223f229a514ad490793313e0a62` |
| `step_operations_ui` | 18.0.2.0.3 | `982d115c726ca58dc4c85bcef1b58e83e44f17bcd4e0748a08c3b172c95bfccd` |
| `step_agricultural_access` | 18.0.2.2.1 | `0d858dde8d0e5d56fb44b3846d2657b5ba32c62ad90c09949e079301fd2b54bb` |
| `step_machinery` | 18.0.21.0.0 | `77a551e233e794238e4333205ddbe204f1e5d0faa1761ad7cb63c8e19d4ac0ad` |
| `step_bpa_irrigation` | 18.0.2.3.1 | `a85615317b40df54416c7e9ec3f2d56a8c644ea0e22ada202a00c44dfa4ea271` |

## 6. Pruebas

Base desechable `MENU_TEST_20260829`, creada desde cero y eliminada al
terminar: **0 failed, 0 error(s)**.

`step_agricultural_access` aporta 9 pruebas nuevas: fusión y archivado de la
raíz, nada alcanzable se pierde, idempotencia, hoja con destino distinto que se
conserva renombrada, app sin gemela que no se toca, ausencia de raíces
duplicadas, dedupe de entradas repetidas en otro nivel, nombres distintos hacia
el mismo modelo que se conservan, y emparejamiento por traducción.

## 7. Respaldos

`/opt/backups/menus_20260829/`

| Archivo | Validación | SHA-256 |
|---|---|---|
| `LAB_TAREAS_menus.dump` | `pg_restore --list` → 29 900 entradas | `a095dd02b11a2cdf80261de79bcea5d9165f5e161534222ac6c00ff535be7f7a` |
| `STEPS_DEMO_menus.dump` | `pg_restore --list` → 29 370 entradas | `14da020a23f9a58376b5fa89ec8665470d2567d11b7b7c22d1f92263bb4e32d2` |
| `dev_addons_menus.tgz` | `tar -tzf` → 171 archivos | `8179e41f5946629c3f2876af3ad549dd9deaf16e9351a7209b39b757533a4098` |
| `demo_addons_menus.tgz` | `tar -tzf` → 171 archivos | `8e141694bac3fcb8d55e424d22ff242c2b295b9f7c60892cb957edcafe06a4d1` |

## 8. Pendientes

1. **Duplicación de fondo del Tracker.** Los modelos `step.tracker.*` siguen
   definidos en `step_hr` **y** en `step_tracker_odoo`. Sólo se quitó el menú;
   sacar el resto de `step_hr` es una refactorización mayor.
2. **Fletes con dos estructuras conviviendo.** Dentro de la app quedan la rama
   heredada (`Orden de flete`, `Tarifa de fletes`, `Tramo de flete`) y la nueva
   (`Órdenes de flete`, `Tarifas`, `Tramos`). Apuntan a lo mismo pero con
   nombres distintos, así que la rutina no las tocó a propósito. Conviene
   decidir cuál queda.
3. **`Gestión y Costos borrador`** sigue publicada como app aparte.
4. El DNS de `stepsapp.cl` estuvo caído durante la madrugada (`NXDOMAIN` en
   8.8.8.8 y 1.1.1.1) y ya se recuperó.
