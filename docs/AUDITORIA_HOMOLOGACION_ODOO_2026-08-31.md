# Homologación Odoo — control del 31 de agosto de 2026

## Resultado: pausada por actividad concurrente y restauración sobre la base principal

Control de solo lectura realizado aproximadamente a las 15:00–15:02 UTC.
No se considera completada la homologación. No se eligió un release canónico,
no se desplegó código, no se actualizaron módulos y no se reiniciaron servicios.
No se copiaron ni modificaron bases desde esta revisión.

## Evidencia comprobada en el servidor

- `odoo18-dev.service`, `odoo18-demo.service` y `odoo18-demo-sys.service`: activos.
- HTTPS `/web/login`: Desarrollo 200 (0,131 s), Demo 200 (0,215 s), Demo-SyS 200 (0,394 s).
- Carga observada al iniciar: 0,45 / 0,16 / 0,08. Esto no sustituye una medición bajo carga.
- Otra sesión ejecutaba una actualización con pruebas de `step_hr_previred`
  en `STEPS_DEMO_SYS_cor2`, usando `/tmp/cor2code` y puerto 8971.
- Había procesos `pg_dump` y `pg_restore` activos. No es posible atribuir
  con certeza todos estos procesos a Claude solo por sus nombres.

## Riesgo que requiere atención del operador de la sesión paralela

Se observó el comando:

```text
pg_dump -Fc STEPS_DEMO_SYS | pg_restore --no-owner --role=demosys_odoo18 --no-acl -d template1 -C
```

La actividad real de PostgreSQL confirma que ese `pg_restore` está conectado a
`STEPS_DEMO_SYS`, no únicamente a una base desechable. Con `-C`, la conexión
inicial a `template1` no demuestra que ese sea el destino final de la restauración.

Cadena observada en `pg_stat_activity` y `pg_blocking_pids`:

| PID PostgreSQL | Proceso | Base | Espera / bloqueo |
|---|---|---|---|
| 1466604 | pg_dump | STEPS_DEMO_SYS | ClientWrite, activo unos 46 minutos |
| 1466610 | pg_restore | STEPS_DEMO_SYS | Lock/relation; bloqueado por 1466604 |
| 1467213 | pg_dump | STEPS_DEMO_SYS | Lock/relation; bloqueado por 1466610, unos 36 minutos |

Sentencia en espera del restaurador:

```sql
ALTER TABLE ONLY public.account_account
ALTER COLUMN id SET DEFAULT nextval('public.account_account_id_seq'::regclass);
```

No se ha establecido si hubo otras sentencias aplicadas antes del bloqueo.
HTTP 200 en el login no garantiza que las operaciones contables estén libres
de bloqueos ni que la restauración no haya afectado previamente otros objetos.

Se avisó al usuario. No se terminaron sesiones ni se liberaron bloqueadores:
liberar el dump sin controlar primero el restaurador podría permitir que
continúe escribiendo sobre la base principal.

## Siguiente paso seguro

1. El operador de la sesión paralela debe confirmar el destino que pretendía
   restaurar, revisar los procesos y detener de forma controlada la restauración
   equivocada si corresponde. Coordinar antes de interrumpir pruebas o copias.
2. Revisar logs y objetos de STEPS_DEMO_SYS para determinar el alcance de las
   sentencias ya ejecutadas. No sobrescribirla con otra base para resolverlo.
3. Confirmar que terminaron pruebas, despliegues y restauraciones.
4. Retomar la comparación de código, módulos instalados, vistas y permisos;
   respaldar antes de cualquier cambio; desplegar secuencialmente solo un
   release probado y compatible.
5. Completar validación autenticada en navegador. No se realizó en este control.

## Diferencia documental para verificar al retomar

`docs/TESORERIA_CORRECCIONES_1_2026-08-30.md` declara Tesorería 18.0.1.2.0
desplegada en Desarrollo y Demo, pero no documenta ese despliegue en Demo-SyS.
Esto es una brecha documental, no una divergencia en vivo confirmada por este
control; debe contrastarse con código y versión instalada una vez que sea seguro.

## Resguardos

No se hicieron nuevos backups porque no hubo escrituras ni despliegues en esta
revisión. No se ejecutaron pagos, correos, documentos tributarios, exportaciones
de datos ni git push. La automatización sigue pendiente de una revisión sin
actividad concurrente; no se declara homologado el sistema.
