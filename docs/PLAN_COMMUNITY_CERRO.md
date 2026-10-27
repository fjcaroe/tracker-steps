# Plan de independencia de Enterprise para Cerro El Plomo

Autorizado por el usuario el 27-10-2026: preparar el plan y comenzar su ejecución,
conservando datos y funcionalidad de los módulos propios. La ejecución empieza
en entornos privados de ingeniería, dentro del circuito de Desarrollo. No se
autoriza una desinstalación masiva en producción ni un refresco de QA-Cerro.

## Criterio de término

La copia convertida debe arrancar con fuentes Community, cero módulos OEEL-1
instalados y sin dependencias Enterprise de los módulos Steps que se publiquen.
Debe conservar maestros, claves, relaciones, históricos, documentos, adjuntos,
permisos y saldos, y aprobar los flujos reales. Ocultar el aviso, cambiar la
fecha de vencimiento o quitar nombres del manifiesto no cumplen este objetivo.

La producción actual sigue siendo Enterprise durante la preparación. El aviso
del 31 de octubre no queda resuelto por las primeras extracciones de código.
No hay una fecha de corte comprometida antes de completar las pruebas.

## Secuencia de trabajo

| Etapa | Trabajo concreto | Condición para avanzar |
| --- | --- | --- |
| 0 Inventario y control | Congelar inventario de módulos, licencias, dependencias, datos y campos manuales. Registrar sustituto y prueba de cada componente usado. Añadir comprobación automática de dependencias. | Evidencia privada reproducible; ninguna pérdida aceptada implícitamente. |
| 1 Base contable | Separar campos, cálculos y formularios multimoneda del motor Enterprise de informes. Preservar IDs, XMLIDs y valores históricos al adoptar campos/vistas. | Arranque puro Community; prueba de actualización en copia fresca de Cerro; integridad de valores e IDs; pagos y conciliación vigentes. |
| 2 Informes y Tesorería | Sustituir accesos y adaptadores a `account_reports` y lotes Enterprise. Evaluar informes OCA y construir adaptadores propios donde se requieran valores operacionales históricos. Desacoplar `step_account_treasury`, sus puentes y T123. | Balance, mayor, antigüedad, flujo de caja, exportaciones y pagos concuerdan con los documentos y permisos. |
| 3 Maestros y personal | Separar maestros agrícolas/operación de `step_hr` respecto de Gantt y Nómina Enterprise. Mantener los modelos, registros y relaciones existentes. Encapsular nómina y entradas de trabajo en puentes. Evaluar motor Community compatible con Simple Digital. | Packing y Productores instalan sin Nómina Enterprise; contratos e históricos conservados; ninguna liquidación pagada recalculada. |
| 4 Exportación y Chile | Separar operación comercial de `l10n_cl_edi_exports`. Implementar/adoptar localización Community y puente DTE compatible con SII. Inventariar certificados, CAF y documentos sin exponer secretos. | Pruebas tributarias y de exportación en ambiente de ensayo; ninguna emisión real durante la migración. |
| 5 Calidad e interfaz | Reemplazar `quality_control`, Gantt y demás extensiones usadas con código propio o componentes Community. Inventariar campos/vistas/reglas heredados y transferir su propiedad antes de retirar Studio. | Flujos completos, no solo portadas; historial y formularios accesibles; campos manuales conservados. |
| 6 Conversión integral | Ensayar el retiro ordenado de Enterprise en una copia actual de Cerro, con fuentes Community exclusivamente. Ejecutar todas las regresiones y conciliaciones. | Cero Enterprise, datos íntegros, restauración ensayada y aceptación funcional. |
| 7 Publicación | Preparar paquete exacto, ventana, respaldo íntegro y bloqueo compartido. Verificar versión, formulario, menú y flujos después de publicar. Migrar QA conservando sus ejercicios mediante un proceso independiente. | Producción verificada; plan de recuperación; evidencia de aislamiento de QA. |

Las etapas 2 y 3 pueden diseñarse de forma independiente, pero cada integración
debe resolver las dependencias de su paquete antes de instalarlo. No se crean
tablas alternativas para los mismos maestros ni sustitutos vacíos de módulos
Enterprise para engañar al cargador.

## Primer paquete en ejecución

Se extrae `step_accounting_multicurrency_core`, LGPL-3, dependiente solo de
`account`. Mantiene los mismos campos en `res.company`, `account.move`,
`account.move.line`, pagos y registro de pagos, y las mismas columnas SQL.
`step_accounting_multicurrency` pasa a ser el puente opcional a los informes
Enterprise; conserva su nombre para no romper a los módulos que todavía lo usan.

La adopción de metadatos crea XMLIDs del núcleo sobre los registros anteriores
y conserva los XMLIDs antiguos como alias. No duplica vistas o campos. La prueba
de retiro de un namespace de alias comprueba la protección nativa de Odoo cuando
otro módulo mantiene la propiedad. Esto no equivale todavía a desinstalar toda
la edición Enterprise ni garantiza el retiro del puente con sus dependientes.

Este primer paquete no desacopla aún Tesorería ni los otros 79 módulos afectados.
Libera una base necesaria y establece el procedimiento para las siguientes
extracciones. Los cambios se mantienen sin publicar en ambientes activos hasta
completar su validación y el circuito de entrega correspondiente.

## Candidatos y decisiones pendientes

- [OCA Financial Reports 18.0](https://github.com/OCA/account-financial-reporting/blob/18.0/account_financial_report/__manifest__.py)
  depende de `account`, `date_range` y `report_xlsx`, con licencia AGPL-3.
  Es candidato para mayor, balance de comprobación y antigüedad. No se ha
  instalado ni se declara reemplazo completo de los informes existentes.
- [OCA Payroll 18.0](https://github.com/OCA/payroll/blob/18.0/payroll/__manifest__.py)
  es candidato a evaluar para el motor Community; no acredita todavía
  compatibilidad con Simple Digital, reglas de Chile ni datos históricos.
- Facturación electrónica chilena requiere una selección y validación específicas;
  no se presume que un módulo de localización genérico sustituye DTE/CAF/SII.
- Las funciones que no se usen se podrán retirar solo después de inventariar
  registros y dependencias; no se interpretan datos vacíos como prueba suficiente.

## Evidencia y continuidad

Inventario inicial: `docs/CERRO_EDICION_Y_DEPENDENCIAS_20261026.md` y artefactos
privados de esa auditoría. Son metadatos de referencia, no un respaldo actual
para una publicación futura. Cada ensayo utiliza una copia fresca del destino.

Validación del primer paquete: `tools/community/validate_finance_foundation.py`.
El script solo acepta bases privadas, toma bloqueo compartido y no tiene modo
de despliegue. Las evidencias, dumps y capturas quedan fuera del repositorio.

Estado y comandos de continuación se registran en
`docs/COMMUNITY_CONTINUACION.md` al terminar esta sesión.

## Avance comprobado al 27-10-2026

Primera extracción completada y validada, sin despliegue en servicios activos:
11 pruebas en una instalación oficial Community con cero Enterprise y 35 pruebas
sobre una copia fresca de Cerro, incluidas las 24 de pagos por factura. Los
valores de 839 tablas y los 21 IDs de campos se conservaron. La huella textual
adicional registra un cambio de escala `15.00`/`15` en envases, sin cambio de
valor. Tres pruebas SQL comprueban que el comparador no redondea importes ni
convierte textos, y dos pruebas validan la conservación de FKs del maestro.

El ensayo Cerro conserva sus 140 Enterprise: es una prueba de extracción, no
la conversión final. Producción sigue con la versión previa y el vencimiento
permanece pendiente. Evidencias y punto exacto de continuación están en
`docs/COMMUNITY_CONTINUACION.md`.

## Segunda extracción: frontera de Tesorería

`step_account_treasury` 18.0.1.3.0 usa el núcleo multimoneda Community.
Los cinco accesos a `account_reports` pasan a `step_account_treasury_reports`
18.0.1.0.0, puente opcional que también conserva el adaptador multimoneda de
informes. Los modelos, cálculos, exportaciones de planificación y permisos de
Tesorería siguen en el módulo original, con sus nombres y tablas.

Al actualizar una base existente se debe instalar el puente en la misma
operación (solo en el ensayo privado, con las demás opciones del validador):

```text
-i step_accounting_multicurrency_core,step_account_treasury_reports
-u step_accounting_multicurrency,step_account_treasury
```

La premigración rechaza
una actualización que dejaría sin propietario los accesos anteriores. Adopta
los cinco menús mediante alias, sin escribir sus acciones, grupos, padres,
secuencias ni estado activo. El hook del puente solo crea los accesos faltantes:
el XML con `noupdate` también escribe al instalar un módulo nuevo, por lo que
no se usa para adoptar estos menús.

Esto es una extracción de dependencias, no la sustitución de los cinco informes.
Una instalación Community dispone de planificación, detalle, resumen y
exportaciones de Tesorería; no anuncia conciliación bancaria, mayor de socios,
estado de flujo de efectivo ni antigüedad Enterprise. En la copia Enterprise
los cinco accesos siguen disponibles con sus IDs anteriores. No desinstalar el
puente ni `account_reports`: todavía faltan sus sustitutos y el tratamiento de
los lotes históricos. La etapa 2 sigue abierta hasta conciliar esos reemplazos.

`tools/community/validate_treasury_extraction.py` ensaya esta frontera en
Community y en una copia fresca de Cerro. Solo admite bases privadas, usa el
bloqueo compartido y no tiene modo de publicación. Además de las huellas de
negocio comprueba campos, menús, ACL, reglas, grupos y membresías.
