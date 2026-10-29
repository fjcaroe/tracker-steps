# T131: creación de sucursales, diagnóstico inicial

Se leyeron descripción, comentario 9788 y adjunto 3430. El documento solo muestra
la pestaña Sucursales, sin el mensaje de error. Solicita Desarrollo, Cerro y QA-Cerro.

La relación estándar es `res.company.child_ids` / `parent_id`. Odoo abre un
formulario de empresa para la sucursal; eso por sí solo no demuestra un fallo.
No crear un maestro paralelo ni modificar datos, permisos o vínculos sin reproducirlo.

## Reproducción privada

`tools/ops/probe_company_branch.py` se ejecutó sobre la copia privada existente
`MANAGEMENT_QA_CERRO_t130c5`, con el usuario operativo existente, sin sudo de ORM.
Se abrió el formulario de la empresa padre, se agregó una línea de `child_ids`,
se ingresó un nombre de prueba y se guardó. Se creó una sucursal con padre correcto
y moneda coincidente. La transacción se revirtió; no se creó ninguna sucursal
real ni se publicó código en un ambiente activo.

El proceso de prueba habilita test_enable únicamente en su proceso privado para
no disparar instalación automática de localizaciones al crear la empresa. No se
modificaron credenciales ni configuración de los servicios. Este caso básico
pasó; todavía no se ha reproducido el error informado y no certifica todo el flujo
visual del navegador o los valores concretos ingresados por el cliente.

## Consulta autorizada

El usuario indicó expresamente preguntar al cliente en el ticket. Se publicó y
verificó el comentario público 9789, solicitando mensaje completo o captura del
error y el paso exacto: Agregar una línea, completar un campo o guardar.
No se repite la consulta por este chat ni se cierra el ticket por este análisis.

T131 queda abierto, pendiente de esa información. No hay un paquete correctivo
ni publicación. Antes de entregar una solución: reproducir la respuesta en copia,
probar funcionalmente el mismo paquete en copias frescas de los tres destinos,
publicar con respaldo y bloqueo y verificar menú, formulario, versión y flujo real.

Artefactos privados: `~/.codex/local-artifacts/t131-20261028/` y
`/opt/steps-validation/t131-branch-repro.log`. No guardar los adjuntos en Git.

## Respuesta 9790 del 29-10-2026

Se leyó el adjunto 3432 completo: el cliente web muestra «Campos no válidos:
Empresa» al guardar el diálogo de sucursal. Empresa es `res.company.partner_id`,
no la matriz `parent_id`. La creación nativa genera ese contacto al guardar.

La vista procesada para el usuario operativo elimina el contacto técnico por
`base.group_no_one`, pero una dependencia del dominio bancario lo reinyecta
invisible con la obligatoriedad ORM. El cliente web combina esa configuración
con el contacto visible de la lista de sucursales: combina invisible con AND y
required con OR, haciendo exigible un contacto aún inexistente. El ensayo Form
inicial no ejercitaba esa combinación del navegador.

Corrección en preparación: conservar explícitamente el contacto técnico oculto,
solo lectura y no exigible por el formulario para todos los usuarios. Mantener
la obligatoriedad y la generación del contacto en ORM. Pruebas de la vista
procesada y de creación nativa con contacto propio; copias y publicación aún
pendientes. No se cierra el ticket por este diagnóstico.

## Avance conservado, revisión automática del 29-10-2026

Paquete candidato `2965b1d3c63ea3fb256430ab0bf98e78eabd3a3f`, SHA-256
`ce035541289a92d4e11fc06cac499c64e4391be55da3653c033ca3cb5cb128c2`.
`step_company_form_restore` sube a 18.0.1.0.1; los dos puentes del paquete
company-form mantienen 18.0.1.0.0. No se cambió la obligatoriedad ORM.

La copia fresca de Desarrollo `MANAGEMENT_QA_DEVELOPMENT_t131d` pasó 13 pruebas,
sin fallos, más menú, formulario procesado del usuario existente, conservación
de vistas específicas y creación de sucursal con contacto propio y matriz/moneda
correctas. La creación de prueba se revirtió. Prueba aprobada en
`/opt/steps-validation/management_development_t131d/qa_passed.json`.

La compatibilidad de Cerro quedó en cola legítima por el bloqueo compartido;
no interrumpir al propietario ni saltarse la exclusión. Proceso lanzado:
`python3 /opt/steps-validation/t131-20261029/tools/ops/manage_management.py compatibility cerro /opt/steps-validation/t131-20261029/company-form-t131.tar.gz t131c --kind company-form --wait-for-lease`.
Log persistente `/tmp/t131-qa-c.log`. Revisar si terminó antes de volver a ejecutarlo.
No se lanzó ninguna publicación ni se cerró T131.

Pendiente: comprobar el resultado de t131c; compatibilidad de QA-Cerro con run
`t131q`; publicar el mismo paquete aprobado en Desarrollo, Cerro y QA-Cerro,
respectivamente con los runs t131d/t131c/t131q y logs
`/tmp/t131-deploy-d.log`, `/tmp/t131-deploy-c.log`, `/tmp/t131-deploy-q.log`.
Cada publicación exige huella inicial vigente, respaldo y bloqueo. Si la huella
cambió mientras esperaba, repetir la copia/pruebas conforme al gestor, sin
forzarla. No refrescar datos de QA-Cerro.

El recolector y registrador existentes aceptan `--ticket 131` y exigen las 13
pruebas por destino, marcador T131 de creación revertida, paquete idéntico y
pruebas de aislamiento antes de permitir el cierre interno silencioso. Revisar
mensajes posteriores a 9790 antes del cierre. Artefactos del gestor en
`/opt/steps-validation/t131-20261029/`; adjuntos locales en la ruta ya indicada.
