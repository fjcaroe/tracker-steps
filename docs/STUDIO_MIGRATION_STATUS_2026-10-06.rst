Pendientes para retirar los desarrollos Studio
==============================================

Resultado: la migración todavía no está completa. Se revisaron por SSH los
cinco ambientes vigentes, su registro cargado, metadatos, vistas efectivas,
menús visibles, reportes y automatizaciones. No se modificaron sus datos ni
se desinstaló Studio durante esta auditoría. Demo, Admin y Everfruit permanecen
fuera del circuito de publicación.

Inventario por ambiente
-----------------------

================= =============== =================== =====================
Ambiente          Modelos manuales Campos manuales     Vistas Studio activas
                                  con dueño Studio
================= =============== =================== =====================
Desarrollo        91              940                 468
Steps / Karo      2               26                  22
SyS               0               3                   13
Demo-SYS          0               3                   14
Cerro El Plomo    0               0                   2
================= =============== =================== =====================

Son objetos técnicos, no cantidades de aplicaciones: incluyen tablas de
líneas, históricos y prototipos. Desarrollo conserva además 15 automatizaciones
Studio activas y tres acciones de reporte Studio. Steps tiene un reporte de
Gastos Studio; SyS y Demo-SYS conservan una acción duplicada de recibo de nómina
y modificaciones de sus plantillas.

Los totales de campos manuales son 968, 32, 35, 38 y 6, respectivamente. La
diferencia comprende campos sin dueño Studio, incluidos campos dinámicos de
planes analíticos y reportes de nómina. No deben borrarse ni migrarse solo por
tener ``state=manual`` o empezar por ``x_``.

Pendientes concretos
--------------------

1. Cerro: pasar a XML versionado las dos personalizaciones activas de listas
   de ``account.analytic.account`` y ``res.company``. No hay modelos ni campos
   manuales con dueño Studio en este ambiente.
2. SyS y Demo-SYS: migrar categoría de empleado, tipo de contrato y cotización
   obligatoria adicional; trasladar a código las vistas y modificaciones del
   recibo de nómina, dirección y formato de impresión. El recibo duplicado debe
   revisarse junto a sus llamadas y vínculos, no eliminarse por su nombre.
   Conservar Simple Digital e históricos sin recalcular liquidaciones pagadas.
3. Steps: migrar Causas del ticket y sus relaciones/acción correctiva/etapa;
   personalizaciones CRM; campos de Gastos, líneas de rendición y su reporte.
   El catálogo de causas contiene registros. Que las líneas de Gastos estén
   vacías hoy no demuestra que pueda retirarse la función que las usa.
4. Desarrollo / Protección Laboral: cursos e inducciones, EPP, accidentes,
   informes y maestros de riesgos/implementos/consecuencias/medidas. El tablero
   Python consulta esos modelos manuales; no los reemplaza. Ley Karin y
   protocolos tienen modelos propios, pero el resto no está migrado.
5. Desarrollo / QA-Inspecciones: inspecciones internas y asesorías externas,
   sus líneas, maestros, estados y folios. El código de controles de calidad
   nativos no elimina los modelos manuales que consulta el tablero.
6. Desarrollo / BPA y Riego: el núcleo de siete modelos ya está definido en
   Python conservando sus nombres ``x_``. Sin embargo, todavía conserva campos
   manuales, tablas de materiales/personal/maquinaria y válvulas, maestros,
   informes y automatizaciones Studio. Completar esas relaciones y cálculos;
   no simplificar las tablas existentes a campos de texto.
7. Desarrollo / Fletes: el núcleo tiene definición Python, pero Tramos,
   Contabilizaciones y Modalidad de frío aún usan formularios/campos Studio;
   también quedan automatización de folios e informe anterior. Revisar las
   relaciones existentes a lugares, fundo y empresa antes de retirar campos.
8. Desarrollo / extensiones compartidas: Unidad de Negocio en Nómina,
   empleados/contratos, productos y plaguicidas/EPP, temporadas, tarifas de
   cosecha, centros analíticos y contactos. Productores y Packing tienen núcleo
   propio, pero el formulario de contactos que comparten todavía hereda los
   campos Studio de asesor externo/relator.
9. Históricos y prototipos: inventariar y conservar Cosecha/Packing anterior,
   planificación/pronóstico, acopio, controles, fumigación y flujo de caja.
   Separar sus menús como historial administrativo no convirtió esas tablas
   a Python. Para retirar Studio también deben conservarse mediante una
   migración trazable o una lectura histórica implementada en código.

Orden y criterio de aceptación
-------------------------------

Comenzar por las extensiones de producción pequeñas y compartidas; después
terminar los bloques agrícolas en Desarrollo. Los destinos siguen la política:
Desarrollo único QA; Demo-SYS solo nómina/soporte; producción autorizada en
SyS, Steps y Cerro. No repartir aplicaciones agrícolas a Demo-SYS para igualar
el inventario. Tampoco reemplazar las versiones agrícolas antiguas de Cerro
sin su paquete, copia de compatibilidad y alcance aprobado.

Cada bloque debe contener definición Python completa, relaciones a maestros
existentes, vistas/acciones/menús/reportes XML, permisos y lógica de las
automatizaciones, además de migración versionada. Preservar filas, IDs,
relaciones, adjuntos y referencias; transferir correctamente su propiedad
de módulo para que una desinstalación no elimine datos convertidos.

La retirada se acepta cuando una copia del destino arranca y ejecuta los flujos
afectados sin depender de definiciones Studio, con reglas por empresa y perfil,
formularios completos y reportes correctos. La desinstalación debe ensayarse
también en esa copia antes de tocar producción. Ocultar el botón Studio o
renombrar los campos no acredita la migración.

Evidencia y límites
-------------------

Inventario completo con ``tools/ops/run_app_audit.py --inventory`` y contraste
de menús/vistas con ``--studio``. La reconciliación versionada es
``tools/ops/summarize_studio_audits.py``. Compilaron 278 vistas primarias de
formulario/lista implicadas en Studio, sin errores; el contraste de menús
tampoco registró errores de vista. Esto prueba estructura efectiva, no la
aceptación de todos los flujos por usuarios ni la corrección de cada cálculo.

Los JSONL completos, conteos de registros y hashes de evidencia se conservan
fuera de Git, en ``~/.codex/local-artifacts/ambientes-canonicos/``. El resumen
privado es ``studio-migration-status-20261006.json``. Las instrucciones
compartidas y el flujo instalado de Claude ahora prohíben expresamente crear
o ampliar modelos, campos, vistas, reportes y automatizaciones Studio.
