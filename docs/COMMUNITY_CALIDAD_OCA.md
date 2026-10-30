# Calidad: contrato neutral y operación OCA candidata

Implementación desde `289e0bab`, posterior a la aceptación H de
[Multifrente](COMMUNITY_MULTIFRENTE.md). No hay aceptación funcional de este
candidato todavía. No cambia dependencias ni código de `step_qa` o
`step_export_traceability`, no retira Enterprise y no acredita Calidad migrada.

## Inventario original y frontera real

El inventario fresco privado confirma en Cerro `quality` y `quality_control`
OEEL-1, `step_qa` 18.0.1.1.0 y `step_export_traceability` 18.0.1.0.1.
Steps no tiene esos consumidores instalados; SyS conserva `quality`.
Se conserva el inventario completo del cierre H y la matriz vigente.

La auditoría nueva consulta **únicamente la copia privada H**, con transacciones
READ ONLY, sin ORM, fuentes OEEL, DDL ni DML. Comprueba dos capturas iguales de
metadata, hashes de filas y secuencias. Observa doce modelos `quality.*`, tres
modelos agrícolas y diecisiete tablas de la familia `quality_`. No hay controles,
puntos ni alertas. Permanecen **19 registros de catálogo**: cuatro etapas,
un equipo, diez tipos de prueba y cuatro motivos. Cero operaciones no elimina
sus modelos, relaciones, permisos, XML IDs ni maestros.

Evidencia privada: `/opt/steps-validation/community-quality-20261030/native-H.json`.
Herramienta: [audit_quality_boundary.py](../tools/community/audit_quality_boundary.py).
Exporta metadata y hashes; no exporta payloads de controles, imágenes ni XML de
vistas. Sus cuatro pruebas puras verifican copia autorizada, protocolo completo,
solo lectura y rechazo de DML; no son pruebas de una inspección.

`step_qa` no declara un modelo de inspección propio: extiende `quality.check`
para su tablero. Inspecciones y asesorías propias ya pertenecen a
`step_agriculture_records`, con sus tablas/IDs originales. La trazabilidad lee
`quality.check` por recepción/movimiento y conserva su semántica de evidencia;
sus campos de panel no son otro libro ni un almacén nuevo.

## Proveedor libre fijado y diferencia de identidad

Se auditó el proveedor primario
[`quality_control_oca`](https://github.com/OCA/manufacture/tree/2d6084f553490408f7a341f05ba6ddd6e641a879/quality_control_oca),
versión 18.0.1.4.0, **AGPL-3**, dependiente de `product`. El pin es
`2d6084f553490408f7a341f05ba6ddd6e641a879` del repositorio OCA/manufacture.
La [declaración de fuentes revisadas](../tools/community/quality_control_oca_source.json)
conserva hashes de manifiesto, modelos, wizard, ACL, vistas y datos leídos;
no afirma contener un snapshot completo de todo el proveedor. La aceptación
debe conservar además el checkout fijado y los bytes realmente instalados.

El motor opera `qc.inspection`, sus líneas y `qc.test` con preguntas y valores
cualitativos/cuantitativos. **No es `quality.check`**. No se retargetean FK,
XML IDs, acciones ni referencias de pallet del proveedor nativo hacia esos
modelos. El vínculo genérico del proveedor libre admite producto; este bloque
no interpreta una inspección de producto como un control individual de cada
pallet o de cada movimiento de recepción.

## Implementación candidata

- `step_quality_contracts` 18.0.1.0.0 contiene contratos funcionales de acceso
  completo y lectura neutral de los modelos agrícolas existentes. No declara
  un modelo vacío, maestro, tabla ni permisos nuevos. La función que exige el
  proveedor original rechaza su ausencia; nunca devuelve `qc.inspection`
  haciéndolo pasar por `quality.check`.
- `step_quality_oca` 18.0.1.0.0 opera los modelos OCA reales. Autoriza actor,
  empresa, preguntas, todas las líneas físicas y todas las respuestas permitidas
  antes del cierre. Rechaza tests vacíos, preguntas duplicadas/ausentes,
  respuestas de otra pregunta, cantidades/unidades incompatibles, límites
  cambiados, NULL físicos, no finitos y prellenado de respuestas como si fuera
  medición. Un cero almacenado puede ser un resultado real; NULL no se convierte
  en cero para aprobar.
- El wizard original y las acciones `action_todo`, `action_confirm` y
  `action_approve` siguen siendo el motor de operación. El cambio de test tiene
  transacción propia. El resultado negativo espera aprobación del responsable
  de Calidad; el acceso directo a un estado no puede inventar un resultado ni
  saltar la secuencia ready/waiting. La aprobación requiere el rol original OCA.
- Se corrige la conversión cruzada de UoM usando la API oficial
  `origen._compute_quantity(valor, destino, round=False)`. Se conservan cantidad
  y unidad observadas; no se escribe una conversión sobre el dato original.
  Las demás evaluaciones continúan el método real del proveedor.
- Los resultados `success`/`failed` y sus observaciones no se reabren ni editan.
  La recomputación de lectura restaura el resultado almacenado sin evaluarlo
  contra criterios actuales. Las respuestas usadas conservan identidad y
  significado. Cancelar una inspección aún abierta conserva el flujo OCA de
  borrador; no se presenta como evaluación aprobada.

Las reglas nuevas aíslan por compañía las líneas, preguntas y respuestas
mediante sus relaciones originales. No se conceden grupos ni ACL. Los métodos
operacionales usan el UID normal incluso con sudo entrante y comprueban acceso
de campo antes de leer. No se crea un resultado o libro paralelo.

`step_qa_native_reference` 18.0.1.0.0 mantiene el proveedor nativo y deriva sólo
el resumen propio a la librería neutral. Conserva modelos, formularios, menús,
acciones, assets e IDs del consumidor existente. Su entrada de trazabilidad
usa el actor normal y exige el proveedor `quality.check` original. No instala
OCA en la referencia nativa ni convierte su almacén.

## Pruebas funcionales preparadas

La revisi�n de ACL originales H confirma que el responsable nativo de Calidad
puede crear equipos y controles y leer tipos de prueba; el usuario de Calidad
s�lo lee los cat�logos. El proveedor OCA concede CRUD de inspecciones/l�neas
al usuario y reserva configuraci�n de tests/preguntas/respuestas al manager.
Los fixtures usan esos roles reales separados; no conceden Settings ni
cambian ACL originales.

Nueve casos OCA usan productos, tests, wizard, preguntas, medidas y acciones
reales: resultado positivo, negativo/aprobación por rol, 1.000 g frente a kg,
lote incompleto/NULL, hijos o respuestas ocultos, permisos de campo/compañía con
caché/sudo, resultados cerrados y criterios usados, test vacío/prellenado/respuesta
ajena y falsificación de resultado/no finitos. Verifican los mismos IDs y datos
almacenados tras rechazos, además de formulario y salida JSON serializable.

Cuatro casos nativos preparan controles reales manuales con tipos originales,
usan sus acciones de pass/fail y el tablero existente, contrastan el resumen
neutral contra la implementación propia anterior, comprueban formularios/aliases
y la identidad de trazabilidad, y deniegan el acceso sin rol incluso con sudo.
Los folios de prueba usan secuencias específicas de su compañía privada; no se
resetea un contador original ni se inventan operaciones productivas.

Estos casos están implementados y compilados, **pendientes de ejecución en el
paquete exacto por el coordinador**. No se suman como trece operaciones de
negocio equivalentes entre motores. La auditoría H y las pruebas puras no
sustituyen esa aceptación funcional.

## Lo que sigue bloqueado

Falta un contrato compatible con la identidad/API nativa: doce modelos,
diecisiete tablas, diecinueve maestros, permisos, puntos, alertas, equipos,
tipos de prueba, referencias de stock y rutas dinámicas. No hay correspondencia
demostrada entre sus registros y el catálogo OCA. Antes de cambiar dependencias
se necesita decidir y probar esa adopción con sus IDs originales, sin tablas
paralelas ni aliases que cambien el significado de una FK.

Por eso las dos aplicaciones originales conservan `quality_control` en sus
manifiestos y su camino Enterprise sigue visible. La operación libre candidata
permite probar un proveedor real y una frontera neutral; no autoriza desinstalar
el proveedor nativo ni publicar el candidato en producción o QA-Cerro.

Mantener las puertas de [Autonomía](COMMUNITY_AUTONOMIA.md): conversión integral
restaurable con cero Enterprise, preservación y aceptación de todos los
productos. No recalcular pagadas, alterar vencimientos, usar
`step_expire_database`, emitir al SII o enviar mensajes externos. Calendar,
Boolean bancario y cuenta 210233 conservan sus restricciones. El 31 sigue en
riesgo alto y no queda resuelto por este bloque de Calidad.
