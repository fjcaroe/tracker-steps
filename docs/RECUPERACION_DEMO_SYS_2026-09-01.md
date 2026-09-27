# Recuperación de Demo-Sys después del refresco — 1 de septiembre de 2026

## Conclusión

El refresco del 31 de agosto reemplazó la base `STEPS_DEMO_SYS` por una copia
de SyS producción. La data productiva nueva quedó disponible, pero el trabajo
quedó incompleto: diez módulos que estaban instalados en Demo-Sys volvieron a
estado `uninstalled`, y dos plantillas laborales configuradas por interfaz no
existían en la base refrescada.

No hubo pérdida irreversible. El respaldo anterior al refresco era válido y
contenía 25.553 objetos restaurables. Se utilizó únicamente para comparar y
recuperar configuración seleccionada. No se restauró sobre la base principal.

## Evidencia antes de corregir

Base anterior al refresco:

- 325 módulos instalados;
- 824 menús activos;
- 192 empleados;
- 387 liquidaciones;
- mejoras Steps de Libro de Remuneraciones, Previred, Contratos/Finiquitos,
  Tesorería, Multimoneda, Colaciones, identidad y portada instaladas.

Base después del refresco:

- 316 módulos instalados;
- 764 menús activos;
- 198 empleados;
- 484 liquidaciones;
- los diez módulos anteriores figuraban desinstalados;
- `steps_hr_payroll_correction` sí estaba instalado y su código existía;
- el usuario `fcaro.ruiz@gmail.com` existía, pero no pertenecía al grupo de
  Administrador del sistema.

Esto explica que el usuario no viera las aplicaciones y mejoras. El módulo de
corrección no se había borrado: faltaba el permiso efectivo y faltaban las
aplicaciones de Nómina que lo rodeaban.

## Método seguro

1. Se restauró el dump previo en una base aislada de auditoría.
2. Se comparó el inventario completo de módulos con la base actual.
3. Se creó un dump fresco de la base actual y una copia aislada.
4. En esa copia se instalaron los diez módulos faltantes. La instalación
   terminó correctamente con 326 módulos y 824 menús.
5. Solo después de esa prueba se detuvo `odoo18-demo-sys.service`, se respaldó
   la base, addons, filestore y configuración, y se aplicó el mismo conjunto a
   `STEPS_DEMO_SYS`.
6. Se recuperaron por ORM las dos plantillas laborales validadas. Sus cuerpos
   conservaron exactamente los hashes SHA-256 del respaldo y no contienen
   variables desconocidas.
7. Las bases temporales de auditoría se eliminaron al finalizar.

## Módulos recuperados

| Módulo | Versión final |
|---|---:|
| `step_account_treasury` | 18.0.1.1.1 |
| `step_accounting_multicurrency` | 18.0.2.0.1 |
| `step_agricultural_branding` | 18.0.1.0.0 |
| `step_colaciones` | 18.0.2.1.0 |
| `step_demo_homepage` | 18.0.1.0.3 |
| `step_hr_contract_lifecycle` | 18.0.2.0.1 |
| `step_hr_contract_lifecycle_simpledigital` | 18.0.1.0.0 |
| `step_hr_previred` | 18.0.3.4.0 |
| `step_hr_previred_simpledigital` | 18.0.2.1.0 |
| `step_hr_remuneration_book` | 18.0.3.3.0 |
| `steps_hr_payroll_correction` | 18.0.1.0.0; ya estaba instalado |

Las acciones, vistas, grupos, menús y perfiles XML del respaldo anterior y de
la recuperación final tienen el mismo inventario para estos módulos. El
adaptador SimpleDigital registró el motor Previred y migró 21 causales de
término al maestro común.

## Configuración recuperada selectivamente

Se recuperaron dos plantillas laborales de Servicios Emca SpA:

- `Pl 1`, contrato permanente, validada;
- `P1 Cto fijo`, contrato a plazo fijo, validada.

No se copiaron objetos transitorios ni historial operacional de la base vieja:
asistentes, lotes Previred anteriores, archivos exportados, logs de Libro de
Remuneraciones, liquidaciones o empleados. Esos registros pertenecían al
dataset anterior y no debían mezclarse con la copia productiva refrescada.

## Caso Sergio Albornoz

La corrección está preservada en la base final:

- término del contrato: 7 de agosto de 2026;
- contrato cerrado;
- cero asistencias posteriores al 7 de agosto;
- liquidación de agosto en estado de revisión;
- chatter: dos asistencias eliminadas y una liquidación recalculada.

## Usuario administrador

`fcaro.ruiz@gmail.com` quedó activo, con contraseña configurada, pertenencia a
Administrador del sistema y acceso al grupo `Nómina: corrección de finiquitos`.
No se imprimió ni almacenó la contraseña en este informe.

## Estado final

- `odoo18-demo-sys.service`: activo.
- `https://demo-sys.stepsapp.cl/web/login`: HTTP 200.
- 326 módulos instalados.
- 824 menús activos.
- 198 empleados y 484 liquidaciones, conservando la data refrescada.
- dos plantillas laborales validadas.
- Desarrollo, Demo, SyS producción y el servicio Odoo principal permanecieron
  activos; no se actualizaron ni reiniciaron desde esta recuperación.

## Respaldo de recuperación

`/opt/backups/demosys_module_recovery_20260901/prod-20260901T235228Z`

Contiene el dump previo a la escritura, addons, filestore, configuración y log
de instalación. El directorio y los archivos tienen acceso restringido.

El respaldo original anterior al refresco se conserva en:

`/opt/backups/demo_sys_refresh_20260831/steps_demo_sys_pre_refresh_20260831.dump`

## Observación

La instalación registra advertencias antiguas de campos obligatorios con datos
nulos en algunos registros importados de producción. Odoo cargó el registro y
los módulos sin fallo, pero conviene corregir esos datos desde los formularios
cuando se trabajen esos contratos o empleados. No se inventaron valores durante
la recuperación.
