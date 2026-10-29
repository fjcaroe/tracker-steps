# Referencia documental positiva SyS — 28-10-2026

Continúa 4b5c384. Se incorpora la respuesta humana: SyS contiene liquidaciones
y procesos reales. Sin nuevas preguntas sobre qué base usar. Lectura SQL forzada,
sin ORM, generación de reportes, recálculos o escritura de negocio en producción.

## Referencia y significado

El caso elegido antes por ser el último de septiembre tiene un PDF preservado,
pero corresponde a un período completo con haberes/líquido cero.
Es válido y se conserva como caso de borde; no acredita cálculos positivos.
El contrato del caso no tiene adjuntos. No se trata el sueldo actual como historia.

El auditor actualizado encuentra 627 done, 626 casos completos sin ambigüedad,
una liquidación con NET 8/32 y cero incompletas. La diferencia respecto de 623
es actividad posterior de la fuente; este agente no creó esas liquidaciones.
Hay 612 casos positivos de períodos anteriores al mes actual. Se selecciona
otro caso completo de septiembre con BASIC/GROSS/NET positivos, sin borrar ni
ocultar casos cero, negativos, ambiguos o incompletos del inventario.

Se exporta el PDF ya adjunto a ese caso: un archivo único, checksum SHA-1 igual
a ir_attachment, tamaño y SHA-256 verificados. No se invoca una acción de
reporte ni una propiedad ORM que pueda leer sueldos actuales. El archivo, texto,
imagen y cápsula contienen datos personales/financieros privados; nunca Git.
El PDF no se modifica. Revisión visual completa de su única página.

compare_sys_reference_document.py verifica vínculo PDF/cápsula por hash, período
exacto y etiquetas únicas en el formato observado. Compara importes almacenados:
BASIC y NET coinciden; GROSS coincide con «Sueldo imponible», pero no con
«TOTAL HABERES», que contiene una asignación no imponible. No se mapea total
haberes a GROSS ni se corrigen los snapshots para igualarlos. El sueldo mensual
impreso se registra como observación documental privada, no como maestro nuevo.

La observación documental aporta una base para un replay futuro aislado. No
certifica cronología de todos los maestros, fórmulas, impuestos, firmas, las
71 reglas ni el resultado financiero/legal. financial_certified y
master_timeline_certified permanecen false. Una impresión preservada no es por
sí sola certificación integral de remuneraciones. La anomalía NET 8/32 sigue
sin resolver; no se escoge ni desactiva una regla por frecuencia o ID.

## Implementación

step_payroll_contracts 18.0.1.8.0 añade select_closed_reference: sobre snapshots
completos, elige el último caso cerrado de un período anterior al actual con
los tres conceptos positivos. Si solo hay casos cero/negativos, devuelve una
referencia explícitamente no positiva; nunca fabrica un importe ni elimina filas.
Excluye abiertos y el mes actual, exige totales finitos y conserva IDs.

audit_sys_payroll_reference.py usa ese mismo helper puro, sin importar Odoo,
y registra su hash. export_sys_reference_document.py copia únicamente el PDF
existente inequívoco de la liquidación seleccionada y conserva prueba de origen.
compare_sys_reference_document.py soporta el formato concreto de una página;
otras etiquetas/monedas/páginas o ambigüedades requieren revisión y fallan.
No se crean modelos, tablas, campos, ACL, aliases ni dependencias nuevas.

El contrato compartido crea liquidaciones con los dos motores reales: positiva
cerrada, cero cerrado posterior, positiva del mes actual y positiva abierta.
Comprueba selección, fallback cero, preservación de las cuatro filas y snapshots
de líneas SQL idénticos. No simula hr.payslip. El caso cero real original sigue
preservado en los artefactos A/F anteriores.

## Aceptación

Paquete D exportado de 1d7e626: 124 pruebas en Community oficial/OCA y 64
en copia fresca aislada de Cerro, cero fallos/errores y cero ERROR de runtime.
Perfil simpledigital: proveedor real instalado en ambos; Community 68 módulos,
cero Enterprise; referencia nativa 383/140. No es conversión histórica.
El perfil es más acotado que book-history: Libro/Previred/HTTP/PDF no cambiaron
y su aceptación previa se conserva; no se suman cifras entre perfiles.

Mismos 95 archivos, fingerprint SHA-256
6a1f76d44ecc9ba8b69e772ce51d26e2ba51f342b785c1c36c7659559a35c1e5.
Pins Community 4b4efe68291d6def5bb7d2e1f2b829e0cda577d4 y OCA
4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e sin cambios. Versión SQL del núcleo
18.0.1.8.0 en ambos. Preservados 919 tablas/proyecciones, 140 contadores,
59.048 XML IDs originales, modelos/campos/ACL/relaciones, 1.614 vínculos
usuario-grupo y 283 implicaciones de grupos. Snapshots de histórico idénticos,
antes/después del upgrade y las pruebas. Tablespaces privados solo para bases
nuevas, sin relaciones públicas en otro espacio. No se migró identidad del motor.

Verificación privada reproducible con el checkout publicado:
python tools/community/summarize_payroll_api.py
~/.codex/local-artifacts/community-sys-document-reference-20261028/evidence-D
--output ~/.codex/local-artifacts/community-sys-document-reference-20261028/summary-D.json.
Valida paquete, helper/auditores/exportador/comparador, versiones, preservación,
origen del PDF, conceptos almacenados y límites de la observación documental.
El comparador de solo lectura está en 86e08af y no modifica bytes de los addons.

C no se acepta: 124/64 pruebas pueden terminar sin fallos de aserción, pero
un fixture que adelantó antigüedad de contrato activó vacaciones del proveedor
y produjo ERROR de permisos. No se relajan ACL ni se oculta el log. D usa períodos
relativos y conserva la fecha contractual original; exige también cero ERROR.
La comparación documental es una ejecución local independiente, de solo lectura,
sobre el mismo PDF/cápsula; no altera el paquete de addons probado.

Artefactos privados locales:
~/.codex/local-artifacts/community-sys-document-reference-20261028/.
Servidor: /opt/steps-validation/community-payroll-sys-document-20261028D.
Conservar paquete, summary-D.json, verification-D.log, pruebas/JSON, PDF original,
document-proof.json y document-comparison.json. No publicar sus importes/IDs ni
el PDF/texto/imagen. Fuentes de las herramientas están versionadas.

## Pendientes y siguiente prompt

Inventario completo releído: Cerro 380 instalados/99 propios/140 EE;
117 manifiestos propios, 22 fuera de Cerro y 54 apps con caminos Enterprise.
Los pins/fuentes privadas siguen comprobados por el validador; matriz sin cambios.
No se retiran dependencias por encontrar un caso documental. Falta la adopción
de identidad/almacén del motor, configuración y certificación de 71 reglas,
entradas/días/YTD/redondeos/asientos, Previred/libro no vacíos, DTE/CAF/folios/
firma/respuestas SII, Tesorería, Calidad, Studio/Documentos/Firma y otros productos.
Falta conversión integral restaurable cero EE y aceptación. El 31 sigue en riesgo
alto; producción conserva Enterprise. Sin despliegue ni refresco QA-Cerro.

Siguiente prompt: continúa desde canónica actualizada en worktree propio. Lee
AGENTS, ambientes, operación, workflow, plan, continuidad, autonomía, matriz,
COMMUNITY_RULE_COLLISIONS.md, COMMUNITY_SYS_DOCUMENT_REFERENCE.md y referencias.
Haz fetch y revisa inventario completo/fuentes privadas. SyS es la referencia
humana real: no preguntar otra vez qué base usar. Usa la nueva cápsula positiva
de septiembre y su PDF existente vinculado por checksum/hash; conserva el caso
cero original como borde. El sueldo impreso es observación documental para
un replay aislado, no cronología maestra certificada. No volver a inferir sueldo
histórico de hr.contract.history actual ni del silencio del tracking. Antes del
replay audita reglas/condiciones/categorías/estructura/entradas/días efectivos del
caso y adopción de sus IDs/permisos; respeta GROSS imponible distinto de total
haberes y la anomalía NET 8/32. No desactives/selecciones reglas para instalar.
Implementa adaptación real y compara borradores nuevos sobre ambos motores,
sin recalcular originales done/paid ni inventar maestros. Si faltan hechos
temporales, conserva el límite concreto y avanza DTE/CAF/SII sin emisión real.
No escribir producción, retirar allí EE, alterar vencimientos o refrescar QA-Cerro.
Respeta Calendar, Boolean bancario y 210233. Usa overlays, respaldos, reserva
5/2 GiB y bloqueo compartido; prueba paquete exacto en Community y copia fresca
de Cerro, guarda evidencia privada, commits/push, integra solo lo validado y
ejecuta python tools/git/verify_handoff.py --require-pushed.


Continuación posterior: [COMMUNITY_PAYROLL_REAL_BASIS.md](COMMUNITY_PAYROLL_REAL_BASIS.md)
cierra BASIC mensual aislado y tipo/código/vistas de días trabajados, con
rollback comprobado. Consultar allí la última aceptación y siguiente prompt;
la certificación financiera y conversión integral siguen pendientes.
