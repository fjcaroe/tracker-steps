# Adaptación de contratos Simple Digital–OCA

## Alcance del bloque

Base canónica `128b9ed`, trabajo en `codex/community-payroll-api-20261027`.
El adaptador LGPL-3 `step_payroll_oca_api` extiende los modelos reales de
OCA `payroll`/`payroll_account`, fijados al commit
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`. No define `hr.payslip` ni
crea un módulo vacío `hr_payroll`. No instala Simple Digital sobre OCA todavía.
Las fuentes efectivas y licencias del proveedor se auditaron en
[COMMUNITY_HR_PAYROLL.md](COMMUNITY_HR_PAYROLL.md).

Contratos implementados:

- Tipo de entrada real `hr.payslip.input.type`, relación restrictiva de la
  entrada al tipo y validación de código, país, estructura, empleado y compañía.
  Conserva el nombre de tabla M2M y columnas comprobados en Cerro; esto prepara
  la adopción futura, pero no acredita que esa adopción ya se haya ejecutado.
- Estructura enlazada al tipo nativo de contratos Community. Regla con FK a su
  estructura primaria, sincronizada con el M2M que realmente calcula OCA.
  No permite quitar una regla primaria del M2M sin mover antes su FK.
- Lectura ORM de importes/cantidad/total por código, con suma de varias
  liquidaciones y permisos del usuario. Los acumulados YTD se rechazan
  explícitamente: no se reemplazan por cero ni por un total mensual.
- Acceso `inputs[code]` y `inputs.get` sobre entradas reales, manteniendo también
  el acceso legado OCA por atributo y su consulta histórica `sum`.
  Las entradas tipadas con código repetido (también mezcladas con entradas sin
  tipo) se rechazan antes de calcular: la agregación del proveedor sigue pendiente.
- `worked_days.get` conserva las líneas reales de OCA. El motor OCA ya entrega
  el registro ORM real `payslip` a las reglas; no fue necesario simularlo.
- Bloqueo de `compute_sheet` si cualquier liquidación está pagada o fuera de
  borrador/verificación. Los tipos ya usados conservan código, país y ámbito.

Las entradas antiguas sin tipo siguen admitidas para respetar el contrato OCA.
No se cambian dependencias de apps instaladas ni se copian reglas chilenas a
un motor incompatible. Cambiar estructura/empleado/compañía/contrato de una liquidación vuelve a
validar sus entradas tipadas, evitando relaciones inconsistentes por API.
Los grupos OCA mantienen sus permisos; solo se añaden
ACL del modelo de tipos: lectura para Nómina y gestión para su responsable.
La conservación de grupos/XML IDs Enterprise al convertir está pendiente.

## Comparación con Cerro

`step_payroll_contracts` contiene pruebas comunes sobre modelos reales.
`step_payroll_enterprise_reference` solo puede instalarse en una base privada
con prefijo `MANAGEMENT_QA_CERRO_PAYROLL_API_`. Ejecuta los mismos contratos
contra el motor actual de Cerro, sin instalar OCA ni el adaptador en esa copia.
Ambas etapas reciben el mismo paquete y comprueban sus huellas, pero instalan
subconjuntos distintos: una comparación de API no es una conversión integral.

`tools/community/validate_payroll_api.py` usa Community oficial limpio y OCA
fijado, bloqueo compartido, overlays privados y una copia nueva de producción.
Desactiva cron y correo únicamente en la copia, conserva el filestore y mide
los datos originales antes/después del upgrade y de las pruebas. Nunca altera
producción, QA-Cerro, vencimientos ni liquidaciones originales pagadas.

## Pendientes obligatorios

1. Adaptar días/ausencias a entradas de trabajo reales:
   `hr.payslip.worked_days.work_entry_type_id` y
   `_get_worked_day_lines_values(domain)`, contratos, jornadas parciales,
   licencias, ausencias y correcciones. No usar días constantes.
2. Adaptar las vistas/XML IDs, grupos y dependencias reales de Simple Digital,
   gastos y sus puentes. Migrar propietario de modelos/campos y M2M conservando
   IDs antes de retirar el motor anterior en una copia.
3. Certificar 71 reglas, cuatro estructuras, seis tipos de entrada, instituciones,
   topes, impuestos, redondeos, cantidades, acumulados y casos chilenos.
   Un asiento genérico balanceado no certifica la contabilización chilena. Las pruebas comunes usan compañía privada en CLP,
   cantidades unitarias y expectativas redondeadas por moneda; no certifican
   jornadas parciales, interacción entre reglas ni todo el redondeo del proveedor.
4. Certificar Previred (dos perfiles) y libro (dos perfiles/42 líneas), con
   comparaciones de archivos/cifras y permisos reales. No publicar datos privados.
5. Probar históricos pagados representativos: Cerro no contiene contratos ni
   liquidaciones originales; las fixtures no sustituyen esa evidencia.
6. Cerrar DTE/CAF/folios/firmas/certificados/respuestas SII y el resto de
   consumidores Enterprise; conversión integral fresca con cero Enterprise,
   restauración, revisión en Desarrollo y aceptación por perfil.

Siguen vigentes Calendar, el override Boolean bancario y `210233` descontinuada.
Producción conserva 140 módulos Enterprise. Las 53 clausuras con Enterprise
sobre 93 apps propias del inventario anterior no bajan por añadir este adaptador.
No hay evidencia suficiente para comprometer una migración integral segura el
31 de octubre de 2026. El riesgo sigue alto y el vencimiento no está resuelto.
