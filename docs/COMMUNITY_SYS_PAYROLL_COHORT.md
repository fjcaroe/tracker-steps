# Nómina de SyS sobre Community

La prueba de octubre de 2026 arranca Odoo 18 Community con OCA Payroll sobre una
copia privada de SyS. El asistente de Previred produjo el mismo TXT v98 que la
referencia nativa de SyS. Los cinco trabajadores admitidos tienen AFP positiva
conciliada con sus líneas originales. Cada fila contiene 105 campos y se
reprodujeron los dos avisos sobre asignación familiar. No hubo anexos ni descartes.
El Libro de Remuneraciones reproduce asimismo las cinco filas, 147 columnas y
SHA-256 `38d10fe52f0b1d41084e86658d33cd2fdbd44d783eeb8bdaf6005992e65f5009`
de la exportaci�n nativa. Ambos archivos de Previred tienen SHA-256
`10c69a74a4454f468acc8040f8fe60ea2361fc9003618f62dbbd071932622dd6`.

## Alcance del arranque

El ensayo con las 336 declaraciones originales mantuvo el grafo restaurado.
El registro oficial Community arrancó sin los modelos de liquidación y del
asistente. Para ensayar el flujo de nómina se restauró una segunda base con
los 2.678 objetos verificados del filestore original. El plan privado registra
las 157 declaraciones apartadas por falta de proveedor admisible, incluidas
las dependientes. Los 142 módulos con licencia OEEL conservan su declaración
original en la base de referencia. La aceptación integral de los demás
productos de SyS sigue pendiente.

En esta cohorte de nómina, el registro usa el proveedor AGPL de Simple Digital
que correspondía a SyS, los proveedores propios y los módulos libres de
Community/OCA. El cierre de dependencias de Previred y de Nómina se comprueba
antes de instalar el motor. Los XML IDs de estructuras, tipos, usuarios,
grupos y datos de nómina siguen perteneciendo a sus registros originales.
La preparación permite a las nuevas referencias OCA de los grupos de nómina
resolver los dos grupos existentes. Las listas de control y las relaciones
originales de usuarios, grupos y reglas están protegidas durante la carga.

La relación de estructura con reglas de SyS es uno a muchos por
`hr.salary.rule.struct_id`. Las 92 reglas pertenecen a cuatro estructuras.
Los consumidores SQL de la interfaz OCA leen una vista de esa FK en tiempo
real, sin duplicar ni asignar reglas. El diario de liquidación sigue la
propiedad de la estructura según la empresa. Las líneas históricas no se
recalculan al introducir el padre opcional de línea de OCA.

## Reproducción

1. Restaurar en una base privada la pareja de SQL y filestore sellados de
   SyS. Generar la referencia nativa con el asistente real. Los archivos con
   contenido laboral quedan en el archivo privado de evidencia.
2. Obtener el inventario desde la fuente real con
   `probe_sys_community_graph.py`. Completar la admisión física y la protección
   de cabeceras y detalles cerrados con `admit_sys_payroll_storage.py` y
   `guard_sys_payroll_history.py`.
3. Sobre otra derivada, aplicar `prepare_sys_payroll_cohort.prepare` y conservar
   su plan privado. `build_sys_payroll_cohort_profile.py` prepara los dos módulos
   libres, las relaciones originales y los manifiestos privados contra las
   huellas revisadas de origen. El código privado del proveedor chileno se
   deriva de su propia versión de SyS.
4. Mantener el bloqueo operativo, el registro sin red, HTTP ni cron y las
   rutas privadas durante la instalación. Encolar los módulos propios por el
   botón de instalación y usar `load_sys_payroll_cohort.py` con el runtime
   oficial. El cargador verifica los dos alias nativos del proveedor antes
   de ejecutar la limpieza normal.
5. Ejecutar `probe_sys_previred_wizard.py` en ambas bases y entregar sus
   registros privados a `compare_sys_previred_receipts.py --native …
   --community …`. Se exige igualdad del TXT, cohorte, importes AFP comprobados,
   diagnósticos, empresa y operador.
6. Cotejar proyecciones, identidades y FKs con `check_sys_payroll_cohort.py`.
   El Libro y el cálculo de borradores tienen comprobaciones independientes en
   `replay_sys_payroll_cohort.py`. Ningún cálculo se aplica sobre liquidaciones
   originales y no se transmiten documentos a entidades externas.
