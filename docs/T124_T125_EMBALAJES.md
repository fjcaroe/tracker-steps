# T124 y T125 — embalajes y listas de materiales

## Solicitud y alcance

Revisión de Helpdesk del 27-10-2026 09:05 America/Santiago. Leídos descripción,
comentarios y adjuntos 3414/3415, incluidas sus capturas. T124 autoriza Desarrollo,
Cerro y QA-Cerro. T125 pide corregir los componentes en Cerro y agregar el mismo
maestro de listas de materiales en Packing. Ambos siguen abiertos.

## Diagnóstico comprobado por lectura

El dominio anterior busca etiquetas de categoría con mayúsculas exactas.
Desarrollo tiene `6 Materiales de embalaje`, mientras Cerro tiene
`6 materiales de embalajes`. Cerro conserva los productos en subcategorías;
no se deben renombrar, copiar ni volver a clasificar para sortear el problema.

## Implementación preparada

`step_packing_packaging_master` 18.0.1.0.0 extiende los modelos originales:

- `product.packaging`: cantidad de clamshell por caja, peso en gramos,
  cajas por pallet, pallets por contenedor, cajas por contenedor de 40 y
  peso neto por pallet. Las dos últimas son calculadas desde sus entradas y
  el campo existente de kg por caja. 204 × 20 = 4080; 3,8 × 204 = 775,2 kg.
  No deriva ni modifica la cantidad incluida, tara o kg por caja originales.
- `mrp.bom`: búsqueda de las mismas etiquetas con `=ilike`, conservando la
  selección por descendientes y el rechazo de maestros ambiguos.
- Packing → Maestros → Listas de materiales de fruta reutiliza la acción,
  formularios, modelo y registros existentes de Exportaciones.
- Cinco pruebas de cálculos/recomputación, valores negativos, categorías con
  minúsculas y descendientes, ambigüedad y reutilización de la acción original.
- El probe comprueba fuente/versiones efectivas, formularios y visibilidad con
  el perfil humano existente; la copia privada además ejerce creación de BOM
  y cálculos con rollback. No basta sintaxis ni HTTP para cerrar los tickets.

El nuevo tipo `packaging-master` del constructor y operador de publicación
incluye solo este addon. No publica los cambios Community de la canónica ni
reemplaza los padres activos de producción. Preserva todos los resguardos del
operador existente: paquete inmutable, copia fresca, huellas de datos/source,
exclusión compartida, respaldo y publicación primero en Desarrollo.

## Estado real y bloqueo de esta revisión

Commit del paquete: `b4548da4e58d72c1ca2bd29c29588a52c23d6c13`.
Rama: `codex/t124-t125-20261027`, subida. Base: canónica hasta `3107162`.
Compilación Python y XML correctos; las pruebas funcionales **aún no corrieron**.
No se publicaron servicios activos ni se cerraron tickets.

El intento `qa development ... t124t125a --kind packaging-master` se detuvo en
la adquisición no bloqueante de `/run/lock/steps-environments.lock`, ocupado por
otro ensayo Community. No se creó la base privada ni se modificó Desarrollo.
No retirar ni saltar el bloqueo, ni detener el otro proceso para continuar.
La base de la siguiente prueba debe corresponder al estado actual del destino.

Paquete inmutable SHA256:
`45949080a91f79c6376becbd1a7afeb7997508239ac109598beb3f08df785380`.

Artefactos privados locales:
`C:/Users/tito4/.codex/local-artifacts/helpdesk-heartbeat-20261027-0905/`.
Contiene auditoría, adjuntos originales, capturas extraídas, paquete y herramientas.
Preparación remota:
`/opt/steps-validation/t124-t125-20261027/`.

## Continuación al liberarse el bloqueo

Leer política, registro privado y cambios canónicos antes de retomar; conservar
la rama pendiente y cambios de otros agentes. Comprobar que el archivo de paquete
mantenga su SHA y que el destino no tenga actualizaciones pendientes.

```text
sudo python3 /opt/steps-validation/t124-t125-20261027/tools/ops/manage_management.py qa development /opt/steps-validation/t124-t125-20261027/packaging-master.tar t124t125a --kind packaging-master
```

Ese run_id es reutilizable solo si sigue sin existir la base
`MANAGEMENT_QA_DEVELOPMENT_t124t125a` y no se guardó `baseline.json`; de otro modo
usar uno nuevo. Corregir fallos reales y generar otro paquete si cambia código.

Después de aprobar: publicar el mismo paquete en Desarrollo, verificar versión,
menú, formulario y flujo real. Ejecutar `compatibility cerro` y
`compatibility qa-cerro` con nuevos run_id, y publicar solo tras aprobar cada
copia y los resguardos de fuente concurrente. No refrescar QA-Cerro. Finalmente
registrar la entrega interna silenciosa según el flujo existente, cerrar solo
los tickets efectivamente verificados, integrar lo probado y ejecutar
`python tools/git/verify_handoff.py --require-pushed`.
