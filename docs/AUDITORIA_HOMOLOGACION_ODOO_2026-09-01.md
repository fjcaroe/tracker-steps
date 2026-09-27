# Homologación Odoo — control del 1 de septiembre de 2026

## Resultado: no homologado; revisión pausada por diagnóstico concurrente de Demo-SyS

No se desplegó código, no se actualizaron módulos y no se reiniciaron servicios.
Los tres servicios estaban activos y los accesos HTTPS respondían 200:

| Ambiente | Tiempo observado |
|---|---:|
| Desarrollo | 0,101 s |
| Demo | 0,086 s |
| Demo-SyS | 0,408 s |

## Desarrollo y Demo

Las listas de módulos Steps instalados y sus versiones coinciden. Los hashes
normalizados de los módulos dirigidos también coinciden, incluidos branding,
portada, Colaciones, Libro de Remuneraciones, Contratos/Finiquitos, Previred y
Tesorería. Ambos tienen `step_account_treasury` 18.0.1.2.0 y
`step_hr_previred` 18.0.3.4.0 instalados.

## Hallazgo crítico confirmado en Demo-SyS

La base conserva información relevante: 29 compañías, 8 usuarios, 905 contactos,
484 liquidaciones y 7.209 asientos. Sin embargo, el registro de módulos muestra
como `uninstalled` los módulos comunes que antes estaban homologados:

- `step_agricultural_branding`
- `step_demo_homepage`
- `step_colaciones`
- `step_hr_remuneration_book`
- `step_hr_contract_lifecycle`
- `step_hr_previred`
- `step_account_treasury`

Solo se observó instalado `steps_hr_payroll_correction` entre los módulos con
prefijo Steps. Esto confirma una regresión funcional en Demo-SyS y es coherente
con la restauración sobre `STEPS_DEMO_SYS` detectada el 31 de agosto.

El código de los módulos comunes sigue presente y coincide por hash con
Desarrollo y Demo, salvo Tesorería, cuyo árbol de Demo-SyS tiene diferencias.
Código presente no equivale a funcionalidad instalada.

## Actividad concurrente

Mientras se revisaba el estado, otra sesión empezó a restaurar el respaldo
`steps_demo_sys_pre_refresh_20260831.dump` en una base de auditoría separada,
`STEPS_DEMO_SYS_AUDIT_PRE_REFRESH`, y estaba inspeccionando
`steps_hr_payroll_correction`. Esa investigación parece dirigida al mismo
incidente. Para no colisionar ni introducir una segunda línea de recuperación,
la automatización no hizo escrituras.

## Respaldo disponible

Existe un respaldo previo a cambios recientes:

`/opt/backups/previred_cor2_20260831/demosys_STEPS_DEMO_SYS.dump`

También existen respaldos anteriores verificados del 29, 28 y 27 de agosto.
No se debe restaurar ninguno sobre la base principal sin comparar primero la
base de auditoría, determinar el punto de corte y preservar cambios posteriores.

## Próximo paso

1. Esperar a que finalice la investigación concurrente y obtener su conclusión.
2. Comparar la base de auditoría con la base principal: módulos, esquemas, datos
   funcionales y cambios posteriores al respaldo.
3. Elegir entre recuperación selectiva o reinstalación/migración idempotente.
   No copiar ni reemplazar la base completa por defecto.
4. Crear un respaldo verificable de la base principal y addons inmediatamente
   antes de corregirla.
5. Reinstalar o actualizar secuencialmente los adaptadores compatibles de
   Demo-SyS, conservar SimpleDigital/SyS y validar Nómina, Libro,
   Contratos/Finiquitos, Colaciones, Previred, Tesorería, portada y permisos.
6. Validar en navegador autenticado y revisar logs antes de declarar homologación.

La automatización debe mantenerse activa: el objetivo todavía no está cumplido.
