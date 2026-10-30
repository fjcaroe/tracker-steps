# Probe del traspaso anclado original

`probe_original_handover.run` se importa en un shell Odoo **ya cargado** por el
coordinador. No abre una conexión, inicia Odoo, instala módulos ni hace commit.
Sólo admite una base privada `MANAGEMENT_QA_CERRO_PAYROLL_API_ORIGINAL_HANDOVER_*`.
El coordinador sigue siendo responsable del respaldo decodificado, el bloqueo
compartido, aislamiento de red y testigos integrales antes/después del proceso.

```python
from probe_original_handover import run
proof = run(env, capsule_path, capsule_sha256, identity_before_path,
            identity_sha256, output_path, actor_uid=None)
```

El default `admission_scope='full'` sigue exigiendo UI. El alcance explícito
`admission_scope='projection-only'` no ejecuta formularios, menús ni renderer,
y requiere el Source nativo real sellado antes de cualquier preparación de ACL.
Conserva todos los contratos de maestros, aliases, reporte completo, MRO,
seguridad y correlativos; usa la misma API normal para materializar/verificar
los 71 pares dos veces. No contiene excepciones por país, registro o menú.

El resumer ofrece `--admission-scope projection-only` y publica un sello
**distinto**, `cohort-projection-admission.json`, privado `0600`. Declara
`ui_scope_exercised=False`, `ui_admission=False`,
`data_projection_scope_passed=True` sólo después de todos los testigos, y
`transaction_committed=True` sólo después del commit real del coordinador.
Persisten los bloqueos de UI, columnas/FK, metadata/serializados, cálculos e
integralidad. Un `passed=True` siempre se interpreta dentro del alcance
registrado; no certifica la aplicación completa.

Un intento posterior puede reutilizar los dos ACL técnicos ya preparados sólo
si cada modelo OCA sigue realmente vacío, cada ACL es único y conserva
exactamente lectura para el mismo gerente, sin write/create/unlink. No se
reescribe un ACL incompatible ni se concede un grupo para reintentar UI.

Para contrastar visibilidad contra el control nativo real, el coordinador puede
añadir `source_visibility_path=...` y `source_visibility_sha256=...`. Se exigen
ambos, archivo privado `0600`, la misma cápsula y el control `REFERENCE` de la
misma restauración. El recibo debe proceder del observer Git `35b9b94d`, con
cursor PostgreSQL readonly real, actor/compañías explícitos y política original
inmutable. Su ausencia conserva la admisión estricta previa; no activa un bypass.

Con ese recibo se usa exactamente el actor/contexto certificado. El Target
ejecuta búsquedas y `read(['id'])` normales para los 120 IDs, y debe reproducir
**cada** permiso y **cada** `AccessError` del Source. Los subconjuntos se derivan
del control observado; no hay listas de países, IDs excepcionales ni conteos
permitidos fijos. Las cuatro estructuras y las 71 reglas deben ser visibles al
actor Source para permitir la API de proyección normal. Los 120 maestros
siguen comparándose por SQL literal, incluidos los que el actor Source no lee.

Se comparan antes/después las ocho tablas de seguridad del contrato Source y
todos sus contadores originales. Una adición de field groups también bloquea;
no se descarta como diferencia legítima sin evidencia adicional. Los contadores
nuevos del Target se enumeran aparte y deben mantenerse exactos durante el
probe. Los snapshots SQL de seguridad del observer fijado se ejecutan fuera
del lexer de formularios, dentro del mismo savepoint; contienen sólo SELECT de
metadata y contadores. No se consulta historia salarial por esa vía.

Los dos archivos de entrada deben ser archivos regulares privados `0600`,
sellados por SHA256, bajo `/opt/steps-validation`. Se exige la cápsula C
`14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140`.
La identidad previa debe contener `original_xmlids`, `ir_model`, `ir_ui_menu` y
el testigo adicional `original_report_462`:

```python
{'table': 'ir_act_report_xml', 'columns': original_physical_column_names,
 'rows_json': [original_postgresql_to_jsonb_report_text]}
```

La falta de ese testigo bloquea antes de escribir. La salida es nueva, privada
`0600`, y contiene hashes/conteos/IDs técnicos; nunca fórmulas ni valores de
configuración salarial. No sobrescribe una evidencia existente.

El probe exige los guardas SQL originales de `run_original_anchor_loader`,
cero Enterprise instalado, proveedores OCA reales y MRO sin `hr_payroll`.
Deriva el ID original del modelo `hr.payslip` de la identidad sellada y compara
las 88 identidades XML originales y el alias del reporte con todas sus columnas
capturadas, incluyendo `noupdate`. Las tres identidades añadidas por el adaptador
de referencia no se cuentan como originales.

Compara literalmente las proyecciones PostgreSQL de columnas originales de los
120 maestros y de las relaciones capturadas, además de todas las columnas
actuales/auditoría de los cinco modelos. La fila completa del reporte original
también debe seguir exacta. Los importes no pasan por `float` ni se recalculan.

Selecciona exclusivamente un gerente legado activo, interno y existente. Si se
indica `actor_uid`, sólo puede seleccionar uno de esos gerentes. No concede
roles ni amplía compañías. Prefiere un gerente sin `base.group_system`; si sólo
existe uno con ese grupo, conserva `su=False` y lo declara en el recibo.

Ejercita cinco formularios primarios explícitos Community, cuatro acciones/menús
reales y la ruta del renderer almacenado del reporte original con ese actor.
Los menús legados se clasifican sin ejecutar acciones ni evaluar sus dominios.
No genera un PDF ni consulta liquidaciones para aparentar un flujo financiero.

La única escritura admisible procede de la API real
`_step_materialize_original_rule_projection` sobre las cuatro estructuras.
Compara sus 71 pares con los `struct_id` originales y repite la llamada para
probar idempotencia. No acepta triggers adicionales en la relación M2M. Un
observador del cursor real delega las consultas sin alterar resultados y
rechaza acceso a tablas históricas/contables, contadores, cursores adicionales
y DML fuera del INSERT concreto de esa API. El guard no sustituye los guardas
SQL ni los testigos integrales del coordinador. Cualquier fallo revierte el
savepoint y emite sólo un código técnico.

Un recibo `passed=True` certifica este subcontrato funcional. Mantiene
explícitamente pendientes la admisión semántica de metadata/serializados,
flujos legados, importes, nómina chilena, PDF, conversión integral y vencimiento.
No es una autorización de adopción o renumeración ni una aceptación global.

La herencia de formularios conserva una excepción SQL limitada: únicamente el
SELECT recursivo de `ir_ui_view` observado en el intento B, hash
`4c0933676ecffd506072359a1b096fe7cf4e2e5ba0117f7d13fad1385ceedcab`.
Se comprueban los dos callers reales base/website, el pin oficial Community
`4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`, los bytes de ambos archivos LGPL
y los hashes de sus métodos/getters mediante AST. No se inspeccionan ni cambian
parámetros; el código SQL debe coincidir byte por byte, incluidos los predicados
de website/active. Cualquier otro `WITH`, variación de contexto, lectura de
historia, función añadida o escritura por flush permanece denegada.

Dentro de la llamada de proyección se admiten también los controles de
savepoint UUID1 generados por la clase real `odoo.sql_db.Savepoint`: creación,
rollback al mismo savepoint y release. Se exige la forma canónica exacta,
fase de proyección activa, objeto/clase/método core reales, mismo cursor y
nombre generado, estado abierto y bytes/AST/pin del archivo LGPL oficial.
No se amplía el lexer general de identificadores ni se admite `COMMIT`,
`ROLLBACK` de la transacción o SQL concatenado. Los nombres y parámetros no
se copian al recibo; sólo se cuentan los controles delegados y su contrato.

El alcance `full` puede recibir explícitamente `source_menu_path` y
`source_menu_sha256`, junto al testigo obligatorio de visibilidad de maestros.
El resumer expone `--source-menu-visibility` y `--source-menu-sha256`; copia
ambos testigos por separado a archivos nuevos `0600`. Sin ese argumento sigue
vigente la comprobación estricta anterior de cuatro menús visibles.

`original_handover_menu_contract.py` admite únicamente el observador nativo
aprobado, el mismo control restaurado, actor/compañías, cápsula, identidad y
políticas preservadas. Compara por concepto la visibilidad real sin debug,
lectura normal del ID del menú y permiso de lectura del modelo de la acción.
Una ocultación procede de la observación sellada, nunca de excepciones por
país, grupo técnico o ID. Los aliases y relaciones originales permanecen
literales; las políticas de menús/acciones/permisos del destino también deben
permanecer exactas antes y después del probe.

Los flags `source_menu_witness_validated`, `source_menu_visibility_parity` y
`core_ui_admitted` sólo se afirman tras sus comprobaciones reales. El último
incluye los cinco formularios y la ruta del renderer; no certifica ejecución de
acciones legadas, cálculos, PDF, importes, metadata semántica o conversión total.
