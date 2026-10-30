# Calidad: operación OCA y referencia nativa validadas en Q4

La pareja privada Q4 del 30-10-2026 pasó **646 casos Community y 441 de la
referencia nativa, sin fallos ni errores**, con el mismo paquete fuente.
Incluye nueve casos de operación OCA y cuatro de consumidores nativos de
Calidad, además de la regresión anterior. Esta es aceptación funcional privada:
no cambia dependencias ni código de `step_qa` o `step_export_traceability`, no
retira Enterprise y no acredita la conversión de Calidad a Community.

El postflight verificó versiones de **31 módulos Community y 27 nativos**,
grafos privados de **120/397 módulos instalados y 0/140 Enterprise**,
respectivamente. La verificación offline confirmó **1.061 contratos de
preservación y 59.079 XML IDs**. Estos resultados pertenecen a las copias
privadas; no describen una conversión de producción. La base anterior es la aceptación D de
[Extensiones operacionales](COMMUNITY_EXTENSIONES_OPERACIONALES.md).

## Inventario original y frontera real

La auditoría privada H observó doce modelos `quality.*`, tres modelos agrícolas
y diecisiete tablas de la familia `quality_`. No había controles, puntos ni
alertas. Los **19 maestros nativos** —cuatro etapas, un equipo, diez tipos de
prueba y cuatro motivos— conservan el proveedor original; no se importan,
sustituyen ni retargetean al catálogo OCA. Cero operaciones no elimina sus
modelos, relaciones, permisos, XML IDs ni maestros.

En Cerro permanecen `quality` y `quality_control` OEEL-1, `step_qa`
18.0.1.1.0 y `step_export_traceability` 18.0.1.0.1. Steps no tiene esos
consumidores instalados; SyS conserva `quality`. La operación OCA validada
no reduce artificialmente sus caminos Enterprise.

La auditoría H usó sólo la copia privada, transacciones READ ONLY, metadata y
hashes de filas/secuencias, con dos capturas iguales. No cargó ORM, cuerpos de
fuentes OEEL ni payloads de controles, imágenes o XML de vistas. Evidencia:
`/opt/steps-validation/community-quality-20261030/native-H.json`.
[audit_quality_boundary.py](../tools/community/audit_quality_boundary.py) tiene
cuatro pruebas puras de copia autorizada, protocolo completo y rechazo de DML;
esas pruebas no se cuentan como inspecciones funcionales.

`step_qa` extiende `quality.check` para su tablero; no declara un modelo de
inspección propio. Los modelos agrícolas siguen perteneciendo a
`step_agriculture_records`, con sus identidades originales. Trazabilidad sigue
leyendo el proveedor original por recepción/movimiento.

## Proveedor libre y custodia del paquete

Se instaló el proveedor real
[`quality_control_oca`](https://github.com/OCA/manufacture/tree/2d6084f553490408f7a341f05ba6ddd6e641a879/quality_control_oca),
18.0.1.4.0, **AGPL-3**, dependiente de `product`, desde el pin público
`2d6084f553490408f7a341f05ba6ddd6e641a879` de OCA/manufacture. No se modifica
su fuente ni se copian cuerpos OEEL.

[quality_vendor_contract.py](../tools/community/quality_vendor_contract.py)
verifica commit, árbol raíz, subárboles y cada blob de sus **114 archivos**,
además de licencia, versión y dependencias. El fingerprint SHA256 del mapa
completo es `dc412934cd1abafc4474813a08a77faebe791ab0ee83001587e46cda25bbc0a9`.
La [declaración de fuentes](../tools/community/quality_control_oca_source.json)
conserva ese contrato y los hashes de los ocho archivos revisados inicialmente.

El checkout limpio y su prueba de procedencia permanecen privados bajo
`/opt/steps-validation/community-quality-20261030/`. El runtime se materializa
dentro del overlay del paquete, con archivos 0644 y directorios 0755; la prueba
Git se crea por separado, exclusivamente y con modo 0600. No se usa como
runtime un symlink que atraviese el padre 0700 del Git privado. Las cuatro
pruebas puras del contrato rechazan alteraciones, omisiones, árboles sobrantes,
licencias/dependencias distintas y destinos ya existentes.

El proveedor opera `qc.inspection`, sus líneas y `qc.test`. **No es
`quality.check`**. No se retargetean FK, XML IDs, acciones ni referencias de
pallet a esos modelos. Su referencia genérica de producto no acredita un
control individual de cada pallet o movimiento de recepción.

## Implementación funcional del paquete exacto

- `step_quality_contracts` 18.0.1.0.0, AGPL-3: acceso completo y resumen neutral
  de modelos agrícolas existentes. No declara un modelo vacío, maestro, tabla
  ni ACL nuevo. Exigir el proveedor original falla si falta `quality.check`;
  nunca devuelve otra inspección como si compartiera su identidad.
- `step_quality_oca` 18.0.1.0.0, AGPL-3: opera el wizard, preguntas, respuestas,
  medidas y acciones reales OCA. Comprueba actor, empresa, campos y todas las
  líneas/respuestas físicas antes del cierre, incluso con caché o sudo entrante.
- `step_qa_native_reference` 18.0.1.0.0, AGPL-3: mantiene el proveedor nativo y
  deriva sólo el resumen propio a la librería neutral. Conserva sus modelos,
  formularios, menús, acciones, assets e IDs. La entrada de trazabilidad usa el
  actor normal y exige `quality.check`; no instala OCA en la referencia nativa.

La preparación del test y el paso a `ready` permiten una observación cuantitativa
todavía sin medir y conservan su **SQL NULL**. No la rellenan con cero. Confirmar,
aprobar o solicitar un estado final exige una medición almacenada y finita,
límites originales válidos y respuestas completas. El caso funcional comprueba
que confirmar sin medir falla sin mutaciones y que registrar después una medida
real permite continuar. Un cero explícito sigue siendo distinto de NULL.

Se rechazan tests vacíos o prellenados, preguntas ausentes/duplicadas, respuestas
de otra pregunta, unidades incompatibles, límites cambiados y valores no
finitos. La conversión cruzada usa la API oficial
`origen._compute_quantity(valor, destino, round=False)` y conserva el valor y
la unidad observados. Las demás evaluaciones continúan el motor real OCA.

El resultado negativo espera aprobación del manager original de Calidad.
Confirmación y aprobación tienen savepoint y no permiten inventar un resultado
mediante escritura de estado. Los resultados `success`/`failed`, sus observaciones
y las respuestas utilizadas no se reabren ni cambian. La lectura/recomputación
de evidencia cerrada restaura el resultado almacenado sin evaluarlo contra
criterios actuales. Cancelar una inspección abierta conserva el flujo OCA.

Las reglas nuevas aíslan líneas, preguntas y respuestas por sus compañías
originales; no conceden grupos ni ACL. El responsable nativo puede crear
equipos/controles y leer tipos de prueba. En OCA, el usuario opera inspecciones
y líneas; el manager configura tests, preguntas y respuestas. Los fixtures
ejercitan esos permisos reales sin añadir Settings ni ampliar roles.

## Evidencia funcional Q4

Los **nueve casos OCA** cubren resultado positivo, negativo/aprobación por rol,
1.000 gramos frente a kg mediante UoM real, preparación NULL y rechazo antes de
confirmar, lote incompleto, hijos/respuestas ocultos, permisos de campo/empresa
con caché/sudo, conservación de resultados cerrados y criterios usados, test
vacío/prellenado, respuesta ajena, falsificación de resultados y no finitos.
Comprueban IDs y datos almacenados tras rechazos, formulario y salida JSON.

Los **cuatro casos nativos** operan controles manuales reales con tipos
originales y acciones de pass/fail, consultan el tablero existente, contrastan
el resumen agrícola neutral con la implementación propia anterior, comprueban
formularios/aliases y la identidad de trazabilidad, y deniegan acceso sin rol
incluso con sudo. Usan secuencias específicas de la compañía privada del fixture;
no se resetea un contador original.

Ambos grupos pasaron dentro de los totales 646/441. No se suman como trece
operaciones de negocio equivalentes entre motores. Las pruebas de operación
libre y la referencia nativa conservan alcances distintos.

## Conversión que permanece pendiente

Falta adoptar un contrato compatible con la identidad/API nativa: doce modelos,
diecisiete tablas, diecinueve maestros, permisos, puntos, alertas, equipos, tipos
de prueba, referencias de stock y rutas dinámicas. No existe correspondencia
demostrada entre esos registros y el catálogo OCA. Antes de cambiar dependencias
se requiere migración versionada que conserve sus IDs, relaciones e históricos,
sin tablas paralelas ni aliases que cambien el significado de una FK.

Las dos aplicaciones originales conservan `quality_control` en sus manifiestos.
Q4 valida una operación libre real y la frontera neutral; no autoriza retirar
el proveedor nativo ni publicar este prototipo en producción o QA-Cerro.

Siguen las puertas de [Autonomía](COMMUNITY_AUTONOMIA.md): productos operativos,
conversión integral restaurable con cero Enterprise, preservación y aceptación.
No recalcular pagadas, alterar vencimientos, usar `step_expire_database`, emitir
al SII ni enviar mensajes externos. Calendar, Boolean bancario y cuenta 210233
mantienen sus restricciones. Este bloque parcial no resuelve el 31 de octubre.
