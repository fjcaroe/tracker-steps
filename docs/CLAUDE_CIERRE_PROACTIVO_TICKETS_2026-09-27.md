# Ejecución proactiva y cierre de tickets de Steps Agro

**Fecha de corte:** 27-09-2026. **Encargo de Fernando:** revisar los tickets abiertos, resolver con acceso al repositorio y a los entornos disponibles, probar, desplegar, dejar evidencia legible en la ticketera y cerrar los tickets cuyo alcance esté cumplido. No terminar en un plan ni dejar un ticket abierto solo porque el cliente no contestó una pregunta técnica que podemos resolver nosotros.

## Autorización operativa actualizada el 30-09-2026

El encargo de resolver y publicar un ticket **ya autoriza** commit, `git push`,
PR, respaldo, despliegue en el ambiente solicitado, actualización de los addons
y servicios afectados, y comentario de entrega. No volver a solicitar permiso
antes de cada paso. Si el ticket o el usuario indica Producción, ejecutar allí
después de pruebas, respaldo y comprobación del destino; si no indica ambiente,
usar Desarrollo/Demo primero y no inferir Producción. Dejar el ticket abierto
solo por un requisito esencial todavía no cumplido o una decisión de negocio
imposible de inferir, explicando exactamente cuál es.

Una aprobación de la interfaz de herramientas o del proveedor de acceso sigue
siendo necesaria cuando el sistema la exige: este Markdown no la sustituye.
No usar la autorización de despliegue para efectuar pagos, registrar asientos
reales ni enviar mensajes externos ajenos al propio ticket.

## Primer ticket: T34 — instalar los módulos Studio en Desarrollo

- [Ticket 34](https://soporte.stepsapp.cl/helpdesk/ticket/34). La solicitud pide tomar las aplicaciones Studio de `https://admin.stepsapp.cl/odoo` e instalarlas en Desarrollo (`https://desarrollo.stepsapp.cl/odoo`). Está en **Nuevo**, aunque ya tiene una nota de implementación y despliegue.
- La evidencia anterior identifica cuatro aplicaciones funcionales cubiertas por tres módulos versionados: Packing Campo y Packing Fruta (`step_packing`), Exportaciones (`step_export`) y Aserradero (`step_sawmill`). Revisar la solicitud y la referencia de Studio para confirmar esa correspondencia; la nota anterior no sustituye la comprobación.
- Comprobación de solo lectura hecha hoy en `LAB_TAREAS`: `step_packing` instalado `18.0.1.0.0`, `step_export` instalado `18.0.2.2.0`, `step_sawmill` instalado `18.0.1.0.0`; `odoo18-dev` activo. La versión de Exportaciones es posterior a la entrega original T34 por el trabajo T35: **no sobrescribirla con la versión vieja** de `origin/ticket/33-packing-export-code`.
- Referencias de código: `origin/ticket/33-packing-export-code` (Packing y Exportaciones, commit `fd087bc`), `origin/ticket/34-aserradero-step-sawmill` (Aserradero, commit `de856bf`). La nota del ticket cita el respaldo `/opt/steps_backups/ticket34_packing_export_dev_20260924T235132Z` y HTTP 200 de la entrega inicial.

### Resultado esperado para T34

1. Leer **descripción completa, adjuntos, notas y cambios posteriores** del ticket; inventariar las aplicaciones, menús y modelos relevantes en Admin y Desarrollo. Separar lo que T34 pidió instalar de las ampliaciones posteriores de Exportaciones en T35.
2. Verificar en Desarrollo los cuatro accesos, vistas principales, permisos y un flujo representativo por aplicación con datos de prueba en una **copia aislada** de la base. Confirmar que el usuario adecuado puede abrirlos, crear y consultar un registro de prueba, y que no aparecen errores de servidor ni de interfaz. Usar la referencia Studio para detectar faltantes reales, sin prometer automatizaciones que Studio nunca tuvo.
3. Si hay un faltante dentro del alcance de T34, corregirlo en una rama/worktree aislado, probarlo, respaldar y desplegar en Desarrollo. Si ya está completo, **no redeplegar por rutina**. No cambiar SyS ni otras bases por este ticket.
4. Guardar un acta Markdown con alcance contrastado, pruebas y resultados, versiones finales, URLs, respaldo si hubo despliegue, commit/PR si hubo cambios, y cualquier parámetro que el administrador pueda editar (ruta exacta del menú, valor actual y cuándo cambiarlo).
5. Publicar en el ticket un comentario en español que resuma **qué se entregó, por qué se implementó así, qué verificamos y qué puede configurar el administrador**. Adjuntar el acta. Abrir la vista del portal para comprobar que el texto tiene párrafos, listas y enlaces legibles y que el adjunto descarga correctamente. Luego pasar T34 a **Solved/Resuelto** si todo el alcance solicitado funciona. Volver a leer la etapa y el mensaje guardado para comprobar el cierre.

## Después de T34: cola sugerida

| Ticket abierto al 27-09 | Próxima acción concreta |
| --- | --- |
| **T25** Guías de despacho | Ya hay evidencia de implementación del modo **proveedor DTE tercero** en Desarrollo y Demo-SyS. Revisar el complemento que pide la variante sin CAF, repetir pruebas funcionales y confirmar el entorno pedido. Cerrar si esa variante cumple el ticket; dejar explícito que la emisión SII con CAF requiere folios/certificados autorizados y no declararla operativa. |
| **T28** Pagos por lotes | El adaptador BancoEstado está desplegado en Demo. Revisar el archivo de respuestas y separar el formato bancario ya entregado de las reglas de aprobación de montos y anticipos sin factura. Resolver técnicamente lo inferible; cualquier dato empresarial variable debe quedar parametrizable y documentado. No afirmar que el ticket completo terminó si una regla central sigue sin definición. |
| **T30** Compras/contratos | Hay documento funcional adjunto y rama `origin/ticket/30-compras-contrato-anticipo`. Auditar código, estado real de despliegue y pruebas; ejecutar lo que falta antes de cerrar. |
| **T22 / T27 / T35** | Revisar las dependencias entre Inventario, Fletes, Guías y Exportaciones, las respuestas ya adjuntas y el estado real de cada módulo. Evitar pedir nuevamente información que ya consta en tickets o se puede leer en Odoo. Trabajarlos uno por uno con acta propia. |
| **T16** Cierre contable Megafrut | Hay una auditoría que detectó riesgo de duplicar o invertir saldos. No registrar asientos ni marcar resuelto basándose solo en una inferencia técnica: cuenta, dirección y fecha deben provenir de una instrucción contable verificable. |
| **T36** «Prueba ticket nuevo» | Confirmar quién lo creó y si era una prueba. Solo entonces cerrarlo como prueba completada o cancelarlo, dejando constancia; no tratarlo como solicitud funcional. |

El listado es una **fotografía** de nueve tickets abiertos, no una orden de cerrarlos todos sin auditoría. Volver a consultar etapas y mensajes antes de cada ejecución. Si T34 se cierra, seguir con T25 sin esperar una nueva asignación, salvo que aparezca una prioridad más reciente en la ticketera.

## Forma de trabajar y de responder al cliente

1. Leer el ticket completo y sus adjuntos, contrastar con código, base, servicio y entregas anteriores. Las preguntas anteriores hechas por la IA son contexto, no un bloqueo automático. Buscar primero la respuesta en el documento funcional, la configuración actual, las prácticas de Odoo y los tickets relacionados.
2. Elegir una implementación razonable y explicar la decisión. Si el cliente puede ajustar un dato —por ejemplo, diario, cuenta, tarifa, bodega, responsable o umbral— dejarlo configurable y decirle **dónde** cambiarlo, **qué valor quedó** y **cuándo** debería hacerlo. No inventar datos empresariales desconocidos.
3. Trabajar en un worktree por ticket. El checkout `C:\Users\tito4\Documents\Odoo` tiene cambios y archivos sin seguimiento; no limpiarlo, cambiarle la rama ni mezclarlo con la entrega. `AGENTS.md` y `CLAUDE.md` describen el despliegue del **Web Tracker**; ese procedimiento solo aplica cuando el ticket modifica ese producto. Para módulos Odoo, verificar la rama y el procedimiento propios de cada entorno.
4. Probar primero en una copia aislada cuando se toquen modelos, datos, permisos, vistas críticas o contabilidad. Usar casos que representen el requerimiento, no solo una prueba de instalación. Antes de desplegar, respaldar lo que se modificará. Tras desplegar, comprobar servicio activo, HTTP, vistas/acciones reales y el flujo del usuario. Conservar en el acta los resultados y las rutas de respaldo; eliminar datos sintéticos de producción si se hubieran creado accidentalmente.
5. Usar las credenciales ya disponibles en el entorno sin copiarlas al Markdown, comentarios, commits ni salida de terminal. La conexión XML-RPC existente lee `C:\Users\tito4\.odoo\helpdesk_api.json`; comprobar su disponibilidad sin imprimir la clave. La VM es `odoo-new` en GCP `stepsconsulting`, zona `us-central1-c`; comprobar base, servicio, ruta de addons y dominio antes de actuar.
6. Para la evidencia visible al cliente, publicar un **comentario** con párrafos, listas y enlaces reales; usar nota interna solo para diagnóstico sensible. En XML-RPC, `helpdesk.ticket.message_post` necesita `body_is_html=True` para interpretar el HTML: usar `tools/post_helpdesk_html.py` y leer `docs/HELPDESK_PUBLICACION_HTML_XMLRPC.md` en la rama de soporte `codex/helpdesk-layout-canonical`. Odoo debe mostrar el formato final, sin etiquetas HTML literales ni Markdown crudo. Revisar también los mensajes antiguos del ticket: si guardaron `&lt;br/&gt;` u otras etiquetas escapadas, respaldarlos y corregir su presentación sin cambiar el texto ni el sentido. Adjuntar el acta y capturas o resultados de pruebas que respalden las afirmaciones. Revisar el resultado en `https://soporte.stepsapp.cl/helpdesk/ticket/<id>` y la ficha de gestión. Las notas internas solo las ve el equipo autorizado.
7. Cambiar la etapa a **Solved/Resuelto** una vez cumplido y verificado el alcance. Si algo imprescindible sigue faltando, precisar el dato único que necesita decidir el cliente y por qué no se puede inferir, resolver el resto, y dejar el ticket en la etapa que represente su estado real. Si queda solo una mejora opcional o un alcance nuevo, abrir o referenciar otro ticket y cerrar el original con la delimitación explícita. Nunca escribir «resuelto» cuando las pruebas o el despliegue fallaron.

## Formato de cierre por ticket

El comentario final debe poder entenderlo alguien que no leyó el código. No usar los términos worktree, rama, commit, PR ni merge: nombrar solo el ambiente (SYS, Cerro el Plomo, Demo, stepsapp.cl) y el ticket. La evidencia técnica (`PR/commit`) va en el trabajo interno, no en el texto al cliente, salvo que el cliente la pida.

> **Ticket TXX resuelto — [resultado concreto].** Implementamos [funciones observables] en [entornos]. Elegimos [decisión relevante] porque [razón breve]. Probamos [flujos y resultados], verificamos [URLs/servicios] y guardamos respaldo en [ruta si aplica]. El administrador puede cambiar [parámetro, valor actual y menú] si su operación requiere otro valor. Evidencia: [acta adjunta, PR/commit, capturas]. [Límite o trabajo nuevo, si corresponde].

Cerrar cada ticket **después** de comprobar que el comentario y adjuntos se ven bien. Al terminar la corrida, entregar a Fernando una tabla breve con IDs trabajados, resultado, enlace al ticket y lo que deba revisar personalmente, si existe.
