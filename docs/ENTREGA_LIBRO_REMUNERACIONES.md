# Entrega — Libro de Remuneraciones consolidado

Módulo: `step_hr_remuneration_book` · **18.0.2.0.0 → 18.0.3.1.0**
Fecha: 2026-08-22 · Entornos: Desarrollo, Demo y una **copia aislada de SyS**.
**Producción y la base original `SyS` no fueron intervenidas.**

Documento complementario:
[AUDITORIA_LIBRO_REMUNERACIONES_EMCA.md](AUDITORIA_LIBRO_REMUNERACIONES_EMCA.md)

---

## 1. Qué hace ahora el módulo

Dos productos separados y dos niveles de permiso:

| Salida | Qué es | Formato | Permiso |
|---|---|---|---|
| **Libro consolidado Excel** | Informe de control interno: 24 columnas por código DT, agrupado por departamento, subtotal por grupo y total general | `.xlsx`, Legal horizontal | exportación completa |
| **Libro consolidado PDF** | El mismo libro y los mismos totales, para imprimir | `.pdf`, Legal horizontal | exportación completa |
| **Archivo oficial DT** | El archivo de carga masiva del LRE, íntegro y sin recortar | `.csv`, `;`, cp1252 | exportación completa |
| **Fichas detalladas por trabajador** | Una página por liquidación con los 20 conceptos DT | `.pdf`, A4 | Nómina |
| **Reporte parcial de remuneraciones** | Acción **distinta**, rotulada como parcial: sólo las liquidaciones que el usuario puede ver. No es el libro de la empresa y **no** ofrece CSV oficial | `.xlsx` / `.pdf` | Nómina |

El libro consolidado **no** se presenta como archivo válido para Mi DT. El módulo
genera el archivo para carga y control; **no declara** ante Mi DT ni confirma su
aceptación.

## 2. Correcciones de esta iteración

### P0 — bloqueantes

| # | Hallazgo | Corrección |
|---|---|---|
| 1 | Libros oficiales incompletos por permisos | Grupo nuevo **«Libro de Remuneraciones: exportación completa»**, implicado por el Administrador de Nómina. Se exige en menú, acción, modelo, informes y rutas HTTP. Si el usuario no ve **todas** las liquidaciones de la compañía en el período, el libro corporativo **se bloquea** en vez de entregar una parte. El Encargado tiene una acción aparte, `Reporte parcial de remuneraciones`, que declara su alcance y nunca ofrece el CSV oficial. |
| 2 | Superficie de lectura configurable (`model_name`, `model_domain` con `safe_eval`, `sudo().search`) | **Eliminada**. Los orígenes externos son ahora **adaptadores registrados en código** (`models/remuneration_book_adapter.py`): un modelo permitido, un campo permitido, parámetros de lista cerrada y dominio construido por el servidor a partir de liquidación, trabajador, período y compañía. Cada adaptador aplica `allowed_company_ids`, filtra por compañía y **verifica registro a registro** que pertenezca al trabajador y período esperados. Los perfiles sólo los edita un grupo técnico o Ajustes; un Administrador de Nómina puede **asignar** un perfil aprobado, no programarlo. |
| 3 | Resolución de perfil no determinística (`candidates[:1]`) | Prioridad 1: perfil **asignado y activo** de la empresa. Si no hay, detección usando **sólo los códigos presentes en las liquidaciones seleccionadas** de esa empresa y período. Coincidencia única ⇒ se usa; cero o más de una ⇒ **bloquea y explica**. Nunca se toma «el primero». La síntesis muestra `Asignado / Detectado / Sin confirmar`. |
| 4 | Validación semántica de perfiles | Restricción **SQL** real `unique(profile_id, dt_code)`; códigos obligatorios; grafo de dependencias con **orden topológico** (no un número fijo de pasadas) que detecta autorreferencias, ciclos y operandos inexistentes; `5210/5201/5301/5501` no pueden configurarse como `zero`; estados **Borrador / Validado / Activo** y sólo un perfil **Activo** puede usarse. Cualquier edición del mapeo devuelve el perfil a Borrador. |
| 5 | HTML sin sanitizar (`sanitize=False` + concatenación) | La síntesis se renderiza con **QWeb** (`views/remuneration_book_preview_templates.xml`) y el campo vuelve a `sanitize=True`. Probado con `<script>`, `onerror=`, comillas, `&` y Unicode: se muestran como texto. |

### P1 — completados en la misma iteración

| # | Hallazgo | Corrección |
|---|---|---|
| 6 | Validación del período en rutas HTTP | Las rutas ya **no aceptan un período escrito a mano**: exigen un asistente del propio usuario más un **token HMAC firmado de vida corta** (300 s). Las fechas y la empresa viajan además como comprobación cruzada y deben ser un mes calendario completo y coincidir con el asistente. Cualquier fallo devuelve `404` sin traceback ni detalle. |
| 7 | Doble construcción y doble auditoría | Una acción del usuario construye **un** dataset. El botón sólo valida (barato) y devuelve la acción; la petición que produce el archivo construye el dataset y registra **exactamente un** apunte de auditoría, con el usuario que inició la acción. Cubierto por pruebas de conteo de llamadas y de logs. |
| 8 | Tolerancia | `CHECK(remuneration_book_tolerance >= 0)` en base más restricción Python. `0` significa **estricta** y ya no se sustituye por el valor por defecto. Negativo se rechaza con mensaje claro. |
| 9 | Formato de RUT | Tres funciones para tres necesidades: `rut_key` (comparar; elimina ceros iniciales), `is_valid_rut` (módulo 11) y `rut_display` (mostrar; **conserva los ceros iniciales**, agrupa con puntos y guion, siempre texto). El CSV oficial **no pasa por ninguna**: se entrega tal cual lo genera la fuente. |
| 10 | Síntesis orientada al usuario | Muestra alcance, perfil y origen de resolución, disponibilidad real de cada salida, liquidaciones, líneas, trabajadores únicos, departamentos, líneas sin departamento, sin RUT, con RUT inválido, trabajadores con más de una liquidación y diferencias de conciliación. Errores bloqueantes separados de advertencias; cuando hay errores, **los botones de descarga desaparecen** y aparece un aviso explícito. Sin nombres, RUT ni montos. |
| 11 | Rendimiento | Recuento de duplicados **O(n)** en una sola pasada (antes `list.count()` por elemento). Adaptadores por lote, prefetch explícito y sin N+1. Línea base medida (§7). |
| 12 | Coherencia documental | Este documento. |

## 3. Arquitectura

```
step_hr_remuneration_book/            38 archivos
├── tools/dt_book.py                  núcleo Python puro: 24 columnas por código
│                                     DT, dataset tipado, alcance, conciliaciones
│                                     y política de RUT
├── tools/xlsx_book.py                layout Steps del Excel consolidado
├── models/
│   ├── remuneration_book_adapter.py  REGISTRO CERRADO de orígenes externos
│   ├── remuneration_book_profile.py  perfil DT ↔ reglas, estados y validación
│   ├── remuneration_book_extractor.py extractor liquidación → códigos DT
│   ├── remuneration_book_log.py      auditoría sin PII
│   ├── res_company.py                perfil y tolerancia por empresa
│   └── hr_libro_remuneraciones_wizard.py asistente, alcance y URLs firmadas
├── controllers/remuneration_book.py  descargas con token firmado
├── report/                           PDF consolidado y fichas individuales
├── security/
│   ├── remuneration_book_security.xml grupos propios
│   └── ir.model.access.csv
├── data/remuneration_book_profiles.xml perfiles semilla (2)
├── views/                            asistente, perfiles y plantilla de síntesis
├── migrations/18.0.3.0.0/            reemplazo de perfiles semilla y bloqueo de
│                                     perfiles con el mecanismo eliminado
├── migrations/18.0.3.1.0/            corrección de reglas identificadoras
├── hooks.py                          implicaciones de grupo y activación honesta
└── tests/                            150 pruebas con datos sintéticos
```

**Fuente única de verdad:** `tools/dt_book.build_dataset()` produce el dataset
que consumen Excel, PDF y la síntesis.

**Extractor propio.** Lee las líneas ya calculadas por el motor instalado y las
traduce a códigos DT con el perfil. No replica ninguna fórmula previsional ni
modifica `l10n_cl_simpledigital_payroll`.

### Adaptadores registrados

| Clave | Modelo permitido | Campo | Parámetros admitidos |
|---|---|---|---|
| `sd_movement_type_rules` | `hr.employee.movement.type` (sólo lee nombre y regla salarial; suma `hr.payslip.line.total`) | `total` | `bono_ok`, `comision_ok`, `aguinaldo_ok`, `movilizacion_ok`, `otros_descuentos_ok`, `anticipo_prestamo` |
| `sd_movement_lines` | `hr.employee.movement.line` | `amount` | `bono_ok`, `comision_ok`, `aguinaldo_ok`, `otros_descuentos_ok` |
| `sd_ccaf_deduction` | `hr.ccaf.deduction` | `installment_amount` | `credit`, `insurance`, `other` |

Añadir un origen exige tocar ese archivo, pasar revisión y desplegar. **No se
puede improvisar desde la interfaz.**

### Perfiles semilla

| Perfil | Reglas identificadoras | Estado real por entorno |
|---|---|---|
| Localización chilena extendida (`l10n_cl_extended`) | `TOTIM,HAB,TDE,LIQ` | **Activo** en Desarrollo, Demo y la copia |
| SimpleDigital (`simpledigital`) | `TOTAL_DSCTOS,GROSS,NET` | **Activo y verificado con datos reales** en `STEPS_DEMO_SYS`. **Borrador** en Desarrollo y Demo, con mensaje accionable: el modelo `hr.employee.movement.type` no existe en esas bases |

Un perfil no se marca validado por el hecho de que el módulo esté instalado: se
valida contra la base concreta, y se revalida en cada arranque del registro
(`_register_hook`), cuando ya están cargados todos los addons.

## 4. Política de RUT (documentada)

| Necesidad | Función | Comportamiento |
|---|---|---|
| Comparar / agrupar | `rut_key` | Quita separadores, K a mayúscula y **elimina ceros iniciales**, para que `0012345678-5` y `12345678-5` sean el mismo trabajador |
| Validar | `is_valid_rut` | Módulo 11 sobre la clave canónica |
| Mostrar (Excel, PDF) | `rut_display` | `12.345.678-5`; **conserva los ceros iniciales** (`007.654.321-K`), K en mayúscula, **siempre texto** — nunca número ni notación científica |
| Archivo oficial DT | — | **No se toca**: se entrega tal cual lo genera la fuente oficial |

Valores sin cuerpo y dígito verificador se devuelven tal cual quedan tras quitar
separadores; la línea se marca en la síntesis (`Líneas sin RUT`, `Líneas con RUT
inválido`) y nunca se descarta.

## 5. Seguridad

- **Grupos propios:** `group_remuneration_book_full` (exportación completa,
  implicado por el Administrador de Nómina) y
  `group_remuneration_book_technical` (edita perfiles, implicado por
  Ajustes/Administración). Son **independientes**: la configuración técnica no
  otorga la exportación completa.
- Las implicaciones sobre grupos ajenos se aplican con el ORM en
  `hooks.ensure_group_implications()`, no en XML: los grupos de `hr_payroll`
  llevan `noupdate="1"` y una actualización desde otro addon se descarta **en
  silencio**, dejando un permiso que parece concedido sin estarlo.
- Rutas HTTP con **token HMAC** ligado a asistente, salida, usuario, empresa,
  fecha y vencimiento; se comprueba con `compare_digest`. Un Encargado no puede
  reutilizar ni adivinar la URL corporativa.
- El permiso se comprueba **antes** de tocar ningún registro, de modo que un
  usuario sin Nómina recibe `404` y no un error de acceso que revelaría que el
  asistente existe.
- Auditoría en `step.remuneration.book.log`: usuario que inició la acción,
  empresa, período, salida, **alcance**, resultado y conteos agregados. `detail`
  guarda el **código** del hallazgo, nunca su mensaje.
- Ningún mensaje, log, síntesis o captura incluye nombres, RUT ni montos.

## 6. Pruebas

**150 pruebas**, todas con datos sintéticos.

| Archivo | Cubre |
|---|---|
| `test_dt_book_tools.py` | código DT, 24 columnas, política de RUT (clave vs. presentación, ceros iniciales, K, siempre texto), agrupación, subtotales, total general, conciliaciones y tolerancia |
| `test_dataset.py` | extracción real: una y dos liquidaciones por trabajador, departamento histórico, respaldos advertidos, sin departamento, sin RUT, RUT inválido, liquidación de término, sólo Hechas/Pagadas, exclusión de otra empresa, totales oficiales no recalculados, perfil incompleto, mes calendario, detección de perfil |
| `test_profiles.py` | perfil explícito, detección única, cero coincidencias, ambigüedad, detección sólo con códigos del período, perfil de otra empresa, perfil no activo, dos empresas con motores distintos; unicidad SQL, códigos obligatorios, totales oficiales que no pueden ser `zero`, autorreferencia, ciclo, cadena larga de agregados, dependencia sin resolver, reedición que vuelve a borrador; adaptadores: campos eliminados, clave no registrada, parámetro fuera de lista, modelo ausente que bloquea |
| `test_adapters_official_csv.py` | disponibilidad del CSV según la fuente instalada, bloqueo con mensaje claro sin fuente, y **por HTTP** que el archivo oficial conserva columnas y delimitador; comportamiento y acotación por compañía de los adaptadores |
| `test_files.py` | Excel: 24 columnas exactas, códigos DT, empresa y período, RUT como texto e importes numéricos, Cantidad vacía en detalle, subtotales y total general, fórmulas con valor en caché, dos hojas, Legal horizontal con encabezado repetido, hoja Control sin datos personales. PDF: mismo dataset y totales |
| `test_preview.py` | XSS con cinco cargas útiles, escapado visible como texto, alcance/origen/disponibilidad en la síntesis, conteos, ausencia de PII, modo parcial sin CSV, errores separados de advertencias |
| `test_audit.py` | el botón no construye dataset, un dataset y un log por archivo, PDF y fichas con su propia salida, previsualización una vez, intento bloqueado registrado una vez y sin PII, usuario real en el log, paridad de totales Excel/PDF |
| `test_security.py` | permisos corporativos y reporte parcial, alcance, CSV bloqueado en parcial, empresa no permitida, aislamiento multiempresa, auditoría sin PII, tolerancia 0/negativa, mes calendario; y por HTTP: descarga con URL firmada, sin token, Encargado que no puede reutilizarla, usuario sin Nómina, token alterado, token vencido, fechas manipuladas, parámetros ausentes, empresa ajena, CSV inalcanzable en modo parcial |
| `test_performance.py` | línea base con 5.000 liquidaciones y recuento O(n) con 20.000 líneas (etiqueta `step_book_perf`) |

### Matriz requisito → prueba → evidencia

| # | Requisito de la suite mínima | Prueba | Evidencia |
|---|---|---|---|
| 1 | Permisos corporativos y reporte parcial | `test_security.TestSecurity.test_payroll_manager_can_generate_the_corporate_book`, `…test_payroll_officer_cannot_produce_the_corporate_book`, `…test_partial_report_is_labelled_as_partial`, `…test_partial_report_never_offers_the_official_csv` | §8 matriz de roles sobre datos reales; captura del asistente parcial en Demo |
| 2 | URL directa por usuario sin permisos | `test_security.TestSecurityRoutes.test_officer_cannot_guess_the_corporate_export`, `…test_user_without_payroll_group_gets_not_found`, `…test_url_without_token_is_not_found`, `…test_tampered_token_is_rejected`, `…test_expired_token_is_rejected` | 404 sin traceback en los cinco casos |
| 3 | Selección y ambigüedad de perfiles | `test_profiles.TestProfileResolution` (7 pruebas) | Compañía B pasó de `profile_not_detected` a detección única tras corregir las reglas identificadoras |
| 4 | Aislamiento multiempresa | `test_security.test_report_of_one_company_never_mixes_another`, `test_dataset.test_other_company_payslips_are_excluded`, `test_profiles.test_two_companies_with_different_engines` | Totales por compañía sin contaminación |
| 5 | Adaptadores permitidos y ataques de configuración rechazados | `test_profiles.TestAdapters` (6 pruebas) | Campos `model_name`/`model_domain`/`amount_field` inexistentes; clave y parámetro fuera de lista rechazados |
| 6 | Grafo de dependencias, ciclos y códigos sin resolver | `test_profiles.TestProfileValidation` (8 pruebas) | Ciclo, autorreferencia, cadena larga y operando inexistente |
| 7 | XSS en previsualización | `test_preview.TestPreviewIsEscaped` (8 pruebas, 5 cargas útiles) | El marcado se muestra escapado; `preview_html` vuelve a `sanitize=True` |
| 8 | Fechas mensuales manipuladas | `test_security.test_manipulated_period_parameters_are_rejected`, `…test_missing_parameters_do_not_leak_a_traceback`, `test_period_must_be_a_full_calendar_month` | Cuatro manipulaciones distintas, todas 404 |
| 9 | Tolerancia cero / negativa | `test_security.test_zero_tolerance_is_strict_and_not_replaced_by_the_default`, `…test_negative_tolerance_is_rejected` | `0` estricta genera la advertencia que `1` absorbe |
| 10 | Un solo dataset y un solo log por acción | `test_audit.TestSingleDatasetAndLog` (8 pruebas) | Conteo de llamadas a `build_dataset` y de apuntes por salida |
| 11 | Paridad de totales Excel ↔ PDF | `test_audit.test_excel_and_pdf_report_the_same_totals`, `test_files.test_pdf_uses_the_same_dataset_and_totals` | Mismos totales, cantidad y grupos |
| 12 | CSV oficial sin columnas alteradas | `test_adapters_official_csv.TestOfficialCsvOverHttp.test_official_csv_keeps_its_columns_and_delimiter` | 147 columnas y ancho uniforme en las 81 filas del caso real |
| 13 | Rendimiento con volumen sintético | `test_performance.TestPerformance` | §7 |

### Resultado exacto

| Entorno | Base | Pruebas | Tiempo | Consultas | Fallos | Errores |
|---|---|---|---|---|---|---|
| Desarrollo | `LAB_TAREAS` | **150** | 40,87 s | 37.759 | 0 | 0 |
| Demo | `STEPS_DEMO` | **150** | 40,98 s | 37.467 | 0 | 0 |
| Copia SyS | `STEPS_DEMO_SYS` | **150** | 43,76 s | 44.100 | 0 | 0 |

Las pruebas de rendimiento corren aparte (`--test-tags step_book_perf`): 4
pruebas, 241 s, 178.806 consultas, 0 fallos.

No se contabiliza ningún error de otros módulos como éxito del Libro. El único
aviso ajeno que aparece en Desarrollo es un módulo `steps_api` ausente del
`addons_path`, anterior a este trabajo.

## 7. Rendimiento (medido, no supuesto)

Desarrollo, 5.000 liquidaciones sintéticas de una compañía, dos departamentos:

| Etapa | Tiempo | Consultas | Tamaño |
|---|---|---|---|
| Construcción del dataset | **4,65 s** | **95** | — |
| Excel consolidado | **0,91 s** | — | 377,2 KB |
| **Total** | **5,56 s** | | |

95 consultas para 5.000 liquidaciones confirma que no hay N+1. El recuento de
duplicados con 20.000 líneas baja a **0,083 s** (era cuadrático).

Con `limit_time_real = 120` en Demo, 5.000 liquidaciones caben holgadamente en
una petición HTTP; **no hace falta generación asíncrona** a este volumen. Si una
compañía superara ~40.000 liquidaciones mensuales habría que volver a medir.

## 8. Validación con datos reales — copia `STEPS_DEMO_SYS`

### Inventario técnico de la copia

| Dato | Valor |
|---|---|
| Origen | base `SyS` de la instancia `odoo-new` (productiva/compartida, servicio `odoo18-sys`) |
| Fecha/hora de corte (UTC) | **2026-08-22T20:13:26Z** |
| Base creada | `STEPS_DEMO_SYS`, propietario `demosys_odoo18` |
| Usuario Linux propio | `demosys_odoo18`, home `0700` |
| Filestore propio | `/opt/demosys_odoo18/.local/share/Odoo/filestore/STEPS_DEMO_SYS` (204 MB) |
| Servicio | `odoo18-demo-sys.service`, **no habilitado al arranque** |
| Escucha | **sólo** `127.0.0.1:8090` (comprobado con `ss`) |
| Publicación web | **ninguna**: nginx no la referencia; no accesible desde la IP pública |
| `dbfilter` | `^STEPS_DEMO_SYS$` · `list_db = False` · gestor de bases **deshabilitado** |
| `STEPS_DEMO` intacta | sí, su servicio sigue con `dbfilter = ^STEPS_DEMO$` |
| Cron | `max_cron_threads = 0` y 24 tareas desactivadas en la base |

Verificación de la copia (sin PII):

| Tabla | Origen | Copia |
|---|---|---|
| `res_company` | 29 | 29 |
| `res_users` | 7 | 7 |
| `hr_employee` | 192 | 192 |
| `hr_payslip` | 387 | 387 |
| `hr_payslip_line` | 5.898 | 5.898 |
| `ir_module_module` | 1.383 | 1.383 |
| ficheros de filestore | 4.342 | 4.342 |

Respaldos en `/opt/backups/libro_remuneraciones/` con SHA-256 registrado:
`SyS_<corte>.dump`, `filestore_SyS_<corte>.tgz`, `STEPS_DEMO_<corte>.dump`,
`filestore_STEPS_DEMO_<corte>.tgz`, más los `.tgz` del módulo por entorno y
`LAB_TAREAS_*.dump`.

### Neutralización aplicada (antes de arrancar el servicio y con cron apagado)

| Acción | Resultado |
|---|---|
| `ir.cron` desactivados | 24 |
| `ir.mail_server` desactivados | 0 (no había) |
| `fetchmail.server` desactivados | 1 |
| Correos en cola cancelados | 1.062 |
| Parámetros `mail.catchall/bounce/default_from` | eliminados |
| Cuentas IAP eliminadas | 3 |
| Conexiones bancarias en línea eliminadas | 3 |
| Proveedores de pago deshabilitados | 17 |
| Compañías con EDI puesto en certificación (`SIITEST`, sin correo de intercambio) | 28 de 29 |
| Usuarios internos desactivados | todos salvo administrador |
| SMS / WhatsApp / push | sin pendientes; sin dispositivos |
| Marca de entorno | `step.entorno = COPIA_DE_PRUEBAS_SYS`, `web.base.url` fijada a `127.0.0.1:8090` |

Comprobación posterior: 0 cron activos, 0 servidores de correo activos, 0 correos
pendientes, gestor de bases deshabilitado.

### Perfil SimpleDigital verificado

Matriz real `código DT → regla / origen SimpleDigital` (sin nombres, RUT ni
montos):

| Código DT | Origen en el perfil |
|---|---|
| 1101 | RUT del trabajador |
| 1115 | días trabajados `WORK100` |
| 2101 | regla `BASIC` |
| 2106 | reglas `GRAT47`, `GRAT50` |
| 2113 | **adaptador** `sd_movement_type_rules` con `bono_ok` |
| 5210 | regla `GROSS` |
| 2302 | reglas `MOV`, `MOV_15` |
| 2301 | regla `COLA` |
| 2311 | regla `ASIG_FAM` |
| 5201 | agregado `5210 + 2302 + 2301 + 2311` (misma fórmula del generador oficial: `5210+5220+5230+5240`) |
| 3141 | reglas `AFP`, `IPS` |
| 3143 | regla `SALUD` |
| 3144 | regla `ISAPRE_EXTRA` |
| 3151 | regla `AFC_T` |
| 3161 | regla `IMP_RETENIDO` |
| 3110 | reglas `CCAF_CREDITO`, `CCAF_SEG_VIDA` |
| 3188 | **adaptador** `sd_movement_type_rules` con `anticipo_prestamo` |
| 3183 | reglas `CCAF_OTROS`, `CCAF_DENTAL`, `CUENTA2` |
| 3155 | regla `APVI` |
| 5301 | regla `TOTAL_DSCTOS` |
| 5501 | regla `NET` |

> **Corrección respecto de la versión anterior:** el mapeo semilla derivado sólo
> de leer el código del proveedor daba `5210 ← habIMP` y `5501 ← NETO`. Contra la
> base real, `NETO` **no existe** (es `NET`) y el generador oficial **no usa**
> `habIMP` para 5210. El mapeo correcto es el de la tabla.

### Conciliación agregada contra la salida del propio proveedor

Se generó el CSV oficial con el generador de SimpleDigital sobre **las mismas
liquidaciones ya calculadas** y se comparó columna a columna. Se publican
**diferencias y conteos**, nunca importes.

| Caso | Liquidaciones | Departamentos | Códigos con diferencia | Diferencia total |
|---|---|---|---|---|
| Compañía A, junio 2026 | 81 | 7 | `5210`, `5201`, `5501` | −3 pesos cada uno |
| Compañía A, julio 2026 | 79 | 6 | `5210`, `5201`, `5501` | −2 pesos cada uno |
| Compañía A, mayo 2026 | 71 | 6 | `5501` | +2 pesos |
| Compañía B, junio 2026 | 12 | 1 | `1115`, `5210`, `5201`, `5501` | +1 día · +3 pesos |
| Compañía C, junio 2026 | 6 | 2 | ninguno | 0 |
| Compañía D, julio 2026 | 9 | 1 | ninguno | 0 |

**17 de los 20 códigos coinciden exactamente, línea por línea, en todos los
casos.**

#### Causa por código DT

| Código | Causa | Resolución |
|---|---|---|
| `5210` | El generador del proveedor calcula el total imponible sumando cada componente **truncado por separado** (`int(float(x))`); el Libro toma el valor oficial de la regla `GROSS`, que redondea una sola vez. La diferencia es de **±1 peso en unas pocas líneas**: 5 de 81, 2 de 79 y 6 de 71 | Se mantiene el valor oficial de la fuente. No se corrige con valores fijos. Es exactamente el fenómeno documentado en la auditoría |
| `5201`, `5501` | Heredan la diferencia de `5210` por la identidad `5201 = 5210+…` y `5501 = 5201−5301` | Igual |
| `1115` | El proveedor lee **la primera** línea `WORK100` y la **trunca** (`int`); el Libro **suma todas** las líneas `WORK100` y **redondea**. Con 29,5 días el proveedor informa 29 y el Libro 30 | **Decisión funcional pendiente de Fernando** (§11). No se cambió nada por cuenta propia |

`5301`, `2101`, `2106` y `2113` coinciden **línea por línea en el 100 %** de los
casos revisados, lo que confirma el mapeo de haberes y descuentos.

### Advertencias encontradas en los datos reales (agregado)

| Caso | Advertencia | Cantidad |
|---|---|---|
| Compañía D, julio 2026 | liquidaciones sin departamento en contrato, liquidación ni trabajador → grupo «Sin departamento» | 9 |
| Compañía A, mayo 2026 | `5201 − 5301 ≠ 5501` por el redondeo descrito | 2 |
| Compañía A, junio 2026 | trabajador con más de una liquidación en el mes (informativo) | 1 |

Ningún caso produjo **errores** bloqueantes.

### Pruebas de acceso con los tres roles, sobre datos reales

| Rol | Libro corporativo | Reporte parcial | Menú libro | Menú reporte parcial | Menú auditoría | Auditoría | Editar perfiles |
|---|---|---|---|---|---|---|---|
| Administrador de Nómina | **OK** (81 líneas, alcance completo) | OK (alcance parcial) | visible | visible | visible | lee | **no** |
| Encargado de Nómina | **Bloqueado**: falta el permiso de exportación completa | **Bloqueado**: 0 liquidaciones visibles para ese usuario | oculto | visible | oculto | sin acceso | no |
| Usuario sin Nómina | **Sin acceso** al asistente | Sin acceso | oculto | oculto | oculto | sin acceso | no |

Que el Administrador de Nómina **no** pueda editar perfiles es intencional: es
exactamente la separación exigida por el hallazgo P0 2.

## 9. Despliegue y hashes

| Entorno | Ruta | Base | Estado |
|---|---|---|---|
| PC | `C:\Users\tito4\Documents\Odoo\step_hr_remuneration_book` | — | fuente |
| Desarrollo | `/opt/dev_odoo18/odoo_agriculture/…` | `LAB_TAREAS` | actualizado, servicio reiniciado |
| Demo | `/opt/demo_odoo18/odoo_agriculture/…` | `STEPS_DEMO` | actualizado, servicio reiniciado |
| Copia SyS | `/opt/demosys_odoo18/odoo_agriculture/…` | `STEPS_DEMO_SYS` | instalado, servicio local |
| Producción | — | — | **no intervenido** |
| Base original `SyS` | — | `SyS` | **no intervenida** |

Los 38 archivos del addon tienen el **mismo SHA-256 en los cuatro sitios**. Hash
del inventario ordenado de hashes:

```
f300cbb74c55135bcefaf886ee71f94e327b7f0954365d9c706b744dc1912b6c   38 archivos, 18.0.3.1.0
```

Se recalcula con:

```bash
find . -type f ! -path '*__pycache__*' ! -name '*.pyc' -print0 | sort -z | xargs -0 sha256sum | sed 's|\./||' | sort | sha256sum
```

Comando de actualización usado en cada entorno (puerto libre obligatorio si el
servicio del entorno está arriba):

```bash
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin -c /etc/dev_odoo18.conf -d LAB_TAREAS -u step_hr_remuneration_book --test-enable --test-tags '/step_hr_remuneration_book,-step_book_perf' --stop-after-init --http-port=8199
```

> Tras actualizar hay que **reiniciar el servicio** del entorno: el proceso en
> ejecución conserva el código Python anterior en memoria y las vistas nuevas
> fallan contra los modelos viejos.

## 10. Respaldo y rollback

Respaldos previos en `/opt/backups/libro_remuneraciones/`:

| Archivo | Contenido |
|---|---|
| `addon_dev_<sello>.tgz` | módulo de Desarrollo, versión anterior |
| `addon_demo_<sello>.tgz` | módulo de Demo, versión anterior |
| `LAB_TAREAS_<sello>.dump` | base de Desarrollo (`pg_dump -Fc`) |
| `STEPS_DEMO_<corte>.dump` + `filestore_STEPS_DEMO_<corte>.tgz` | Demo completa |
| `SyS_<corte>.dump` + `filestore_SyS_<corte>.tgz` | origen de la copia |

Rollback de un entorno:

```bash
sudo tar xzf /opt/backups/libro_remuneraciones/addon_dev_<sello>.tgz -C /opt/dev_odoo18/odoo_agriculture/
sudo -u odoo /usr/bin/python3.10 /opt/odoo18/odoo-bin -c /etc/dev_odoo18.conf -d LAB_TAREAS -u step_hr_remuneration_book --stop-after-init --http-port=8199
sudo systemctl restart odoo18-dev.service
```

Los modelos y campos añadidos son **aditivos**: volver atrás no destruye datos de
nómina. La migración `18.0.3.0.0` **recrea** los perfiles semilla; conserva y
restaura la asignación por empresa buscando el perfil por su código técnico.

Retirar la copia por completo:

```bash
sudo systemctl stop odoo18-demo-sys && sudo systemctl disable odoo18-demo-sys
sudo -u postgres dropdb STEPS_DEMO_SYS
sudo rm -rf /opt/demosys_odoo18
sudo rm -f /etc/odoo18-demo-sys.conf /etc/systemd/system/odoo18-demo-sys.service
sudo systemctl daemon-reload
```

## 11. Pendientes reales antes de instalar en la base original `SyS`

1. **Decisión funcional sobre `1115` (Días).** El archivo oficial DT trunca y lee
   una sola línea `WORK100`; el libro interno suma todas y redondea. Alternativas:
   (a) dejarlo como está y documentar la diferencia de hasta 1 día por línea;
   (b) alinear el libro interno con el archivo oficial para que ambos documentos
   cuadren a la vista. **No se cambió nada sin tu decisión.**
2. **Elegir con SyS/SimpleDigital el período y las compañías de referencia** y
   contrastar el libro Steps con el libro que hoy usan como referencia impresa,
   no sólo con el generador del proveedor.
3. **Datos de origen a corregir en SyS**, detectados en la copia: liquidaciones
   sin departamento en contrato, liquidación ni trabajador (9 en un caso). El
   libro las agrupa en «Sin departamento» y lo advierte, pero conviene corregir
   el dato.
4. **Confirmar la política de permisos con el cliente**: quién debe tener
   «exportación completa» y quién se queda con el reporte parcial.
5. **`SyS` tiene `list_db = True`.** No es un cambio de este trabajo y no se tocó,
   pero conviene ponerlo en `False`: expone el selector de bases de esa
   instancia.
6. **Retención de la copia.** Propuesta: conservar `STEPS_DEMO_SYS` y sus
   respaldos **sólo mientras dure esta validación**, con un máximo de 30 días
   desde el corte (2026-08-22), y borrarlos con el procedimiento de §10.
   **No se ejecutará ningún borrado sin tu autorización.**
7. **Usuarios de prueba en la copia**: `prueba_administrador_nomina`,
   `prueba_encargado_nomina` y `prueba_sin_nomina`, creados **sin contraseña**
   (no pueden iniciar sesión por navegador). Se eliminan junto con la copia.

## 12. Revisión visual realizada

En navegador, con la sesión ya autenticada del agente:

- **Desarrollo** — menú `Nómina › Reportes` con *Libro de Remuneraciones*,
  *Reporte parcial de remuneraciones* y *Auditoría del Libro de Remuneraciones*.
  Asistente: alcance «empresa completa», perfil resuelto con su origen
  (`Detectado`), síntesis con los conteos y la disponibilidad de las cuatro
  salidas, bloque de advertencias sin nombres, RUT ni montos, y diálogo con
  scroll correcto y botones fijos en el pie.
- **Desarrollo, período vacío** — aviso rojo «No es posible generar el informe»
  con el motivo, **los cuatro botones de descarga desaparecen** y sólo queda
  *Cancelar*. Sin traceback.
- **Demo** — mismos menús. *Reporte parcial de remuneraciones* se muestra con
  aviso ámbar, alcance «Alcance parcial» y **sin** el botón *Archivo oficial DT
  (CSV)*.

Las capturas usan únicamente datos sintéticos de Desarrollo y Demo.

### Lo que no pudo hacerse en navegador

| Punto | Motivo | Cómo reproducirlo |
|---|---|---|
| Capturas del *Encargado* y del *usuario sin Nómina* | Iniciar sesión como otro usuario exige introducir credenciales, algo que no está dentro de lo que puedo hacer | Los tres roles están verificados de forma automática (§8 y `test_security.py`): permisos, menús, acciones y códigos HTTP. Para la captura basta con iniciar sesión con cada usuario de prueba |
| Ancho tipo tablet | La ventana del navegador autorizado está maximizada y no admite el redimensionado remoto | Reducir la ventana a ~768 px y reabrir el asistente; el formulario usa `<group>` estándar de Odoo, que colapsa a una columna |

## 13. Repositorio y primer commit — **recomendación, sin ejecutar**

El addon sigue **sin seguimiento** (`??`) en el árbol de trabajo. No se añadió a
ningún repositorio ni se hizo `push`.

**Recomendación:** el repositorio actual (`fjcaroe/tracker-steps`) es **público** y
este módulo es propiedad intelectual de Steps con lógica de nómina de clientes;
**no debe publicarse ahí**. Propongo un repositorio **privado** nuevo,
`steps-odoo-addons`, con un directorio por addon, y este módulo como primer
contenido.

Inventario del primer commit (38 archivos, sin `__pycache__`):

```
__init__.py, __manifest__.py, hooks.py
controllers/{__init__.py, remuneration_book.py}
data/remuneration_book_profiles.xml
migrations/18.0.3.0.0/{pre-migrate.py, post-migrate.py}
migrations/18.0.3.1.0/post-migrate.py
models/{__init__.py, remuneration_book_adapter.py, remuneration_book_profile.py,
        remuneration_book_extractor.py, remuneration_book_log.py,
        res_company.py, hr_libro_remuneraciones_wizard.py}
report/{__init__.py, remuneration_book_report.py, remuneration_book_report.xml}
security/{remuneration_book_security.xml, ir.model.access.csv}
tests/{__init__.py, common.py, test_dt_book_tools.py, test_dataset.py,
       test_profiles.py, test_adapters_official_csv.py, test_files.py,
       test_preview.py, test_audit.py, test_security.py, test_performance.py}
tools/{__init__.py, dt_book.py, xlsx_book.py}
views/{hr_libro_remuneraciones_wizard_views.xml,
       remuneration_book_profile_views.xml,
       remuneration_book_preview_templates.xml}
```

Estrategia sugerida:

1. Crear el repositorio **privado** vacío.
2. Añadir un `.gitignore` con `__pycache__/`, `*.pyc`, `.env*`.
3. Primer commit sólo con el addon, mensaje
   `feat(hr): libro de remuneraciones consolidado 18.0.3.1.0`.
4. Rama `main` protegida y trabajo por PR.
5. **Nunca** añadir dumps, filestore, credenciales ni el Excel de referencia.

**A la espera de tu autorización.** No se ejecutó `git add`, `git commit` ni
`git push`.
