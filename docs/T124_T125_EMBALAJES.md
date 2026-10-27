# T124 y T125 — embalajes y listas de materiales

> Entrega completada en los tres destinos y tickets cerrados. Estado vigente y
> evidencia en `docs/T124_T126_ENTREGA_20261027.md`. Lo siguiente es historia de
> los ensayos y decisiones; sus pendientes quedaron superados por esa entrega.

> Actualización posterior al mensaje humano de los cuatro tickets: el ensayo
> de Cerro aprobó las cinco pruebas y la conservación de datos, pero el flujo
> de usuario detectó otra configuración faltante. No se publicó en Cerro.

> Estado vigente al cierre de la revisión de las 11:00 del 27-10-2026:
> Desarrollo publicado y verificado. Cerro y QA-Cerro pendientes. Los apartados
> iniciales conservan la historia del primer ensayo; usar la continuación final.

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

## Revisión de las 11:00 — Desarrollo entregado

El ensayo A aprobó cinco pruebas, pero la comparación detectó cambios de
`write_uid`/`write_date` al inicializar los campos calculados nuevos. Se añadió
un pre/post-init versionado: conserva los registros originales en tabla TEMP,
rechaza cualquier cambio de valores de negocio o IDs y restaura únicamente
esos dos campos de auditoría. No se ocultaron diferencias de cantidades.

Paquete **vigente**: commit `0d548e874ca927c191ab793b90bac1482850f300`, SHA256
`bb2aa8969b0fc554eccf30defd8dbba01a7aa9b7e74d790374ac29921b7f30ce`.
Archivo remoto `/opt/steps-validation/t124-t125-20261027/packaging-master-B.tar`.
El paquete A anterior no es la entrega aprobada.

Copia B: `MANAGEMENT_QA_DEVELOPMENT_t124t125b`, cinco pruebas aprobadas,
comparación de datos aprobada y probe con usuario existente aprobado. Se corrigió
solo el fixture del probe para asignar la empresa del producto al embalaje;
se recertificó sin repetir una batería que no cambió. Probe en commit `3f43aab`.

Publicado en Desarrollo con respaldo íntegro:
`/opt/steps_backups/management_development_20261027T140414Z/`.
Overlay `/opt/steps-managed/releases/development/0d548e874ca927c191ab793b90bac1482850f300/`.
Versión efectiva 18.0.1.0.0, fuentes, formulario, menú y once materiales
seleccionables comprobados con usuario 2, no superusuario. No se alteraron los
padres activos ni se publicaron los paquetes Community.

La publicación en Cerro y QA-Cerro se detuvo **antes de empezar** por el bloqueo
compartido de otro ensayo Community (`community-labor-20261027F`). No terminar
ese proceso ni retirar la exclusión. T124/T125 siguen abiertos hasta completar
ambos destinos. T126 también está preparado; ver `docs/T126_CODIGO_ARANCELARIO.md`.

Al retomar con el bloqueo libre, usar el paquete B ya publicado en Desarrollo:

```text
sudo python3 /opt/steps-validation/t124-t125-20261027/tools/ops/manage_management.py compatibility cerro /opt/steps-validation/t124-t125-20261027/packaging-master-B.tar t124t125c --kind packaging-master
sudo python3 /opt/steps-validation/t124-t125-20261027/tools/ops/manage_management.py deploy cerro /opt/steps-validation/t124-t125-20261027/packaging-master-B.tar t124t125c --kind packaging-master
sudo python3 /opt/steps-validation/t124-t125-20261027/tools/ops/manage_management.py compatibility qa-cerro /opt/steps-validation/t124-t125-20261027/packaging-master-B.tar t124t125q --kind packaging-master
sudo python3 /opt/steps-validation/t124-t125-20261027/tools/ops/manage_management.py deploy qa-cerro /opt/steps-validation/t124-t125-20261027/packaging-master-B.tar t124t125q --kind packaging-master
```

Comprobar antes que cada run_id sea nuevo. Si hay cambios de origen/configuración,
el operador debe rechazar la publicación y exigir otra copia fresca. Después
comprobar aislamiento con `tools/ops/provision_cerro_qa.py verify`, sin acciones
create/resume/publish ni refrescos. El cierre interno silencioso queda protegido
por `tools/helpdesk/record_packaging_species_delivery.py` y exige evidencia de
los tres destinos, ninguna respuesta humana posterior no revisada y ausencia
de notificaciones. No ejecutarlo con pruebas parciales.

## T125 — decisión requerida sobre la jerarquía real

La categoría `6 materiales de embalajes` no contiene físicamente las categorías
`6.1 materiales de caja` y `6.2 materiales de pallet`: las tres tienen
`parent_id` vacío. Por tanto, corregir las mayúsculas no basta para que el
dominio nativo `child_of` encuentre los veinte productos de estas dos categorías.
No son productos perdidos ni un problema demostrado de permisos.

Se preguntó al usuario mediante pregunta asíncrona si deben vincularse como
subcategorías del maestro de materiales (manteniendo productos e IDs) o seguir
separadas y usar selección explícita de categorías. **No inferir la respuesta**.
No renombrar, reclasificar, duplicar ni reparentar categorías mientras esté
pendiente. Si elige vincularlas, preparar y probar una configuración explícita
por destino, conservando relaciones/IDs y comprobando su efecto contable antes
de publicar. Si deben seguir separadas, usar relaciones al maestro existente
para el selector y el dominio; no resolverlas por texto o IDs fijos.

Prueba de Cerro detenida antes de aceptación/publicación:
`/opt/steps-validation/management_cerro_t124t125c/`, cinco pruebas aprobadas,
pero sin `qa_passed.json` porque el probe no encontró materiales seleccionables.
No certificarla hasta resolver y probar la decisión. Cerro y QA-Cerro continúan
sin este paquete. Desarrollo mantiene la entrega ya comprobada.

## Decisión humana recibida y ejecución de la jerarquía

El usuario respondió: **vincular ambas como subcategorías**. La decisión queda
autorizada; no volver a preguntarla. El adaptador
`tools/ops/packing_material_hierarchy_setup.py` toma una configuración explícita
por destino de esas categorías únicas existentes. No crea categorías, no cambia
`categ_id` de productos y comprueba que las cuentas efectivas de cada material
en todas las empresas se conserven. Rechaza otro padre, ambigüedad, nuevos
descendientes o cambios concurrentes frente al plan.

La comparación permite exclusivamente padre, ruta, nombre completo derivado
y auditoría de las dos categorías aprobadas. Nombres originales, IDs y demás
campos se conservan; las demás categorías y documentos se comparan completos.
El adaptador verifica la estructura y cuentas antes de confirmar. Se requiere
otro ensayo de Desarrollo (sin cambios de jerarquía allí) y copias frescas de
Cerro/QA con ese mismo adaptador. La autorización no acredita su publicación.

## Simulación comprobada con la decisión aprobada

Sobre `MANAGEMENT_QA_CERRO_t124t125c`, la aplicación del adaptador en una
transacción con rollback vinculó las dos categorías y conservó sus veinte
productos, todos los IDs y las cuentas efectivas de esos productos en todas las
empresas. Con el usuario existente 6 de Cerro (empresa 2), aparecieron veinte
materiales y pasó el flujo nativo de crear una lista y seleccionar componentes.
El probe terminó con rollback: no acredita una publicación ni cambió producción.
Evidencia privada: `hierarchy-rollback-probe.log` en la carpeta de esa copia.

Nuevo ensayo fresco de Desarrollo **en cola**, a la espera del bloqueo compartido:
`management_development_t125hier1`, con el mismo paquete B y el adaptador aprobado.
Sesión exec del chat 70559. No duplicar ese proceso: comprobar sus logs y
`qa_passed.json`. Después hacer copias frescas de Cerro y QA con el mismo
adaptador. Los run_id antiguos sin prueba aprobada no sirven como aceptación.

T126 ya aprobó dos pruebas y el flujo nativo en `management_development_t126d`.
Su publicación únicamente en Desarrollo está ejecutándose/en cola en la sesión
85093; el operador espera el bloqueo **antes** de leer la línea base y conserva
los resguardos de actualización, respaldo y verificación. No lanzar otro deploy
hasta comprobar esa operación. Cerro/QA de T126 todavía no se publicaron.
