# Continuidad horaria de la migración Community

Autorización del usuario, 28-10-2026: continuar cada hora con GPT Sol, esfuerzo
medio y acceso local completo hasta completar la migración de los productos
propios. La automatización debe trabajar en este mismo hilo. El usuario gestiona
los restablecimientos de cuota; no se compran créditos ni se modifican límites.
La programación no garantiza cuota ni disponibilidad de la máquina.
Se verificó el contexto efectivo del hilo: gpt-6.1-sol, esfuerzo medium,
approval_policy never y sandbox danger-full-access. El heartbeat continúa este
hilo y hereda sus ajustes; no es un permiso para publicar en producción.

## Inicio de cada ejecución

1. Leer AGENTS.md, ~/.odoo/environments.json, OPERACION_ODOO_CANONICA.md,
   WORKFLOW_GIT_COMPARTIDO.md, PLAN_COMMUNITY_CERRO.md, COMMUNITY_CONTINUACION.md,
   el último documento de aceptación (actualmente COMMUNITY_PREVIRED_SIMPLEDIGITAL.md) y esta hoja. Hacer fetch de la canónica
   origin/codex/ambientes-canonicos-reparacion; partir del último estado integrado.
2. Revisar el inventario completo antes de implementar. La matriz
   COMMUNITY_INVENTARIO_ENTERPRISE_20261028.md distingue 95 apps propias instaladas,
   52 con clausuras Enterprise pendientes y los módulos propios fuera de Cerro.
   Auditar también fuentes privadas instaladas, imports, vistas/JS/assets,
   modelos y datos efectivos. Cero dependencias declaradas no prueba equivalencia.
3. Elegir un bloque concreto que desbloquee la siguiente puerta. Registrar una
   hipótesis comprobable y trabajar en worktree propio. No tocar cambios ajenos.
   Evitar solapar actualizaciones; usar /run/lock/steps-environments.lock.

## Orden de trabajo y puertas de aceptación

| Frente | Estado y condición de cierre |
| --- | --- |
| Núcleos agrícolas, operacionales y Tesorería | Extracciones probadas; falta adoptar sus puentes/consumidores en el paquete integral y probar menús/formularios/flujos por rol. |
| Simple Digital–OCA | Instalar el proveedor real, adoptar campos/XML IDs/ACL/FK/M2M sin perder identidad; certificar reglas, días y ausencias, entradas repetidas, redondeo, YTD, asientos, Previred y libro. No simular hr.payslip. |
| HR y consumidores | Cerrar los restantes puentes de Tarjas, liquidaciones, entradas, libros, gastos y exportaciones; solo después cambiar dependencias. |
| DTE/CAF/SII | Auditar licencia/API e implementar motor real compatible: CAF, folios, firma, documentos y guías/exportación, respuestas y reintentos, históricos. Solo entornos aislados de prueba; ninguna emisión real. |
| Contabilidad/Tesorería restante | Lotes, conciliación, pagos y consumidores; preservar saldos y el Boolean bancario legado, sin reactivar 210233. |
| Calidad, Studio, Documentos/Firma, interfaz | Inventario de modelos/campos/automatizaciones/adjuntos, alternativas funcionales y permisos. Respetar los límites visuales Calendar. |
| Resto de productos propios | Incluir módulos no instalados en Cerro y fuentes fuera del repo. Probar instalación y flujo real, no solo manifiestos. |
| Conversión integral | Copia fresca de Cerro que arranque y opere con fuentes Community exclusivamente, cero EE, identidad/relaciones/permisos/históricos/saldos/correlativos comparados; recuperación ensayada y aceptación en Desarrollo. |

## Límites permanentes

El acceso completo permite operar las herramientas, no levantar las restricciones
funcionales. No escribir en producción, retirar allí Enterprise, cambiar
vencimientos ni refrescar QA-Cerro. No recalcular liquidaciones pagadas o
validadas. No sustituir maestros por texto, inventar valores de salud/pensión,
crear tablas paralelas ni módulos Enterprise vacíos. Conservar licencias/autoría;
no copiar código OEEL. No publicar documentos comerciales, reglas privadas,
respaldos, datos personales ni credenciales. No enviar mensajes externos.

La fecha 31-10-2026 mantiene riesgo alto hasta superar la conversión integral;
ningún bloque parcial, prueba sintética ni tarea programada resuelve el vencimiento.

## Cierre de cada ejecución

Probar el paquete exacto en Community oficial y copia fresca aislada de Cerro,
con overlays privados, respaldo y comparación antes/después. Diferenciar prueba
de referencia nativa de conversión real. Ante un fallo, corregir y repetir la
aceptación en bases frescas; conservar diagnóstico fuera del checkout.

Guardar commits útiles y subir la rama. Integrar solo bloques revisados y
validados en la canónica sin sobrescribir avances concurrentes. Ejecutar
python tools/git/verify_handoff.py --require-pushed antes de anunciar cierre.
Actualizar continuidad con commit, alcance, evidencia privada reproducible,
pendientes concretos y próximo prompt. No repetir suites ya verdes sin cambios
que lo justifiquen. Avisar solo progreso significativo, fallo o acción necesaria.
Si falta una fuente/configuración crítica, avanzar en otro frente verificable y
conservar visible el bloqueo; no fabricar resultados ni declarar completado.

La migración solo termina al cumplir todas las puertas de la tabla; entonces
informar el resultado acumulado y finalizar la programación. No desplegar el
corte de producción automáticamente: requiere el paquete integral y la decisión
operativa de corte del usuario.


## Retención y reserva de espacio — autorización 28-10-2026

El usuario autorizó eliminar respaldos antiguos para evitar falta de espacio.
Antes de un ensayo comprobar el volumen de SHOW data_directory, no solo /opt.
Mantener 5 GiB libres en PostgreSQL y 2 GiB en artefactos; si no alcanza, no
crear/restaurar ni insistir sobre una base incompleta. pg_restore se detiene
al primer fallo y conserva el log privado.

Se pueden retirar copias de ensayos propios inactivas y dumps obsoletos mediante
un plan explícito revisado y tools/community/cleanup_payroll_rehearsals.py, bajo
el mismo bloqueo. Conservar una referencia reciente validada, casos dorados
necesarios y respaldos recientes totalmente decodificados; preservar código,
logs y JSON de aceptación. No aplicar planes ya consumidos ni adivinar propiedad
por un nombre genérico. Nunca DROP FORCE, terminar sesiones ajenas, borrar
producción/QA-Cerro ni copias de otros productos sin autorización específica.
El plan y resultado deben quedar privados y su resumen versionado en continuidad.
