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
