# T93 y T94 en Cerro El Plomo

Estado: publicado y verificado en Cerro El Plomo; T93 y T94 resueltos.
Fecha de la solicitud: 19-10-2026, America/Santiago.

## Autorización y contenido

T93 fue aprobado en el comentario 9521 («Aplicación aprobada / Actualizar cerro
el plomo»), y T94 en el comentario 9518 («Aprobado / Actualizar cerro el plomo»).
Estas respuestas posteriores autorizan la promoción de estas aplicaciones al
destino; los publicadores originales conservan su restricción a Desarrollo.

Paquete de promoción: commit `b4fde1eead445caa44ba24da146900302cd667e6`, SHA-256
`ab6c2bc14a87ee852fb9c69e9b930217480b74f23075324a95141a28da4098c9`.

| Módulo | Versión | Entrega de Desarrollo de origen |
| --- | --- | --- |
| step_inventory_packing | 18.0.1.2.4 | 8e564010deba5e543013e839b71038d81061da02 |
| step_packing_operations | 18.0.2.8.3 | bfc2430f5b593f399a5774e8251ea79c21df3997 |
| step_packing_dispatch | 18.0.1.0.1 | bfc2430f5b593f399a5774e8251ea79c21df3997 |
| step_packing_sag | 18.0.2.0.0 | bfc2430f5b593f399a5774e8251ea79c21df3997 |
| step_export_traceability | 18.0.1.0.1 | 32b884ede0e87503f7ce3f1883ca1876e5e4b87e |

Se comparan los 111 archivos y versiones con los manifiestos originales y se
comprueba también el hash del archivo original en disco. El paquete no modifica
el código de negocio revisado. El publicador exige ambas aprobaciones, la prueba
del mismo paquete en Desarrollo, una copia fresca del destino y un respaldo con
bloqueo compartido y ausencia de downgrade/cambios concurrentes.

La copia inicial de Cerro encontró que Inventario Packing estaba en 18.0.1.2.2 y
no definía `step_document_company_id`, utilizado por la vista aprobada de OT en
las tarjas. Se incorporó la versión 18.0.1.2.4 ya utilizada en Desarrollo como
prerrequisito nativo. Su migración conserva los textos históricos y añade
relaciones a documentos existentes a partir de los embarques explícitos; no
deduce vínculos por nombres. La copia fallida no se reutiliza para acreditar la
promoción. El paquete previo de cuatro módulos tampoco es la prueba final.

La siguiente copia detectó que, durante la carga de la definición base de
Inventario, Odoo intentaba sustituir temporalmente las claves de categorías ya
unificadas por el catálogo anterior. El procedimiento de Cerro utiliza un
adaptador temporal en el proceso de actualización para conservar únicamente las
relaciones canónicas que ya existen y están validadas. No cambia IDs ni crea
copias de los maestros. El servicio normal no carga ese adaptador; los modelos
siguen utilizando la extensión de categorías unificadas instalada previamente.
La comprobación final exige las cuatro relaciones canónicas y sus FK validadas.

El paquete completo pasó 46 pruebas sin fallos y 11 comprobaciones funcionales
en `MANAGEMENT_QA_DEVELOPMENT_t93t94native`, con conservación de los registros.
Su prueba está en
`/opt/steps-validation/management_development_t93t94native/qa_passed.json`.

La copia fresca `MANAGEMENT_QA_CERRO_t93t94canonical` pasó también las 46 pruebas
sin fallos ni errores y las 11 comprobaciones funcionales. Conservó todos los
valores anteriores y las cuatro FK canónicas validadas. Evidencia:
`/opt/steps-validation/management_cerro_t93t94canonical/qa_passed.json`.

## Conservación y alcance

Destino: `CERRO_EL_PLOMO`, servicio `odoo18-cerroelplomo.service`, configuración
`/etc/odoo18-cerroelplomo.conf`, <https://cerroelplomo.stepsapp.cl>.
Desarrollo sigue siendo el único QA público. La copia privada de Cerro utiliza
sus propios datos, con correo y cron desactivados y puerto HTTP en localhost.

La conservación compara todas las columnas anteriores de las tablas de negocio,
incluidas cuentas, inventario, documentos y maestros. Solo excluye columnas
añadidas por la instalación; no ignora valores antiguos ni cambios de fecha.
Los overlays son privados y no sustituyen raíces compartidas con otros destinos.

El inventario previo de Cerro tiene cero tarjas E y cero inspecciones nativas,
una OT y un embarque. No se crean tarjas, aprobaciones SAG ni documentos de
prueba permanentes para completar el panel. Las pruebas funcionales adicionales
usan transacciones descartadas. El listado aparecerá al existir tarjas E reales.
La solicitud y certificación SAG siguen siendo externas.

## Evidencia

Los adjuntos, respuestas humanas, inventario, paquetes, logs, comprobantes y
capturas quedan fuera del repositorio, en
`~/.codex/local-artifacts/t93-t94-respuestas-20261019/`.
Las herramientas de publicación y pruebas están versionadas en `tools/ops/`;
la anotación interna de entrega requiere evidencia funcional y visual del destino.

## Publicación y cierre

El servicio de Cerro quedó activo con las cinco versiones de la tabla y el
paquete exacto probado. Respaldo previo:
`/opt/steps_backups/management_cerro_20261020T004054Z`.
Overlay privado:
`/opt/steps-managed/releases/cerro/b4fde1eead445caa44ba24da146900302cd667e6/`.
Se utilizó el bloqueo compartido `/run/lock/steps-environments.lock`.

La comprobación posterior en producción pasó las ocho verificaciones SAG y las
tres de trazabilidad, con fixtures descartados, y confirmó las cuatro relaciones
canónicas y sus FK validadas. No se añadieron datos operativos de prueba.

Se verificó en el navegador, con Cerro El Plomo SpA activa, la navegación
Packing / Inspecciones / Inspección SAG, la lista, el formulario nuevo, los
campos y acciones de archivos/anexos y los once tipos de servicio. Se descartó
el formulario nuevo sin guardar. También se abrió Exportaciones / Recibidor /
Trazabilidad y se comprobaron el título y las columnas de las siete etapas.
La lista de Cerro está vacía por ausencia de tarjas E; los flujos completos con
pallets se acreditan mediante las pruebas funcionales transaccionales.

Las siete capturas se conservan en el directorio privado de evidencia. El archivo
`cerro-visual-review.json` vincula sus hashes al commit y SHA del paquete, a las
46 pruebas y al log de la copia final `cerro-canonical.log`. El registro de
entrega valida esas evidencias y vuelve a comprobar que no haya respuestas
humanas posteriores pendientes antes de cerrar.

Se registraron notas internas sin destinatarios ni notificaciones: T93, mensaje
9522; T94, mensaje 9523. Ambos tickets quedaron en etapa 4, verificada por lectura
posterior. No se enviaron correos ni mensajes a terceros.
