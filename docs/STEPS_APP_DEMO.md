# Steps App — demostración reproducible (datos sintéticos, Odoo de prueba)

Todo corre en un ambiente **desechable**: una base llamada `demo`, creada y borrada por el script. El script y el sembrado se **niegan** a
trabajar sobre una base cuyo nombre no empiece por `demo`/`test`. No usar jamás contra una base de un cliente.

## 1. Requisitos (una vez)

| Pieza | Cómo |
| --- | --- |
| Odoo 18 | `git clone --depth 1 --branch 18.0 https://github.com/odoo/odoo.git $ODOO_HOME/odoo` + entorno virtual con `requirements.txt` (sin `python-ldap`; `psycopg2-binary`). Para el inicio de sesión con Google en un Odoo real: `google-auth`. |
| PostgreSQL | Servidor local y un rol `odoo` con permiso de crear bases (`createuser -s odoo`). |
| `step_mobilization` | Solo existe en `develop`: `git archive origin/develop step_mobilization \| tar -x -C $EXTRA_ADDONS`. Es una dependencia, no se copia al repositorio. |
| Node 22 | `cd mobile && npm ci`. |

Variables (con los valores usados al preparar esta entrega): `ODOO_HOME=/opt/odoo-env`, `ODOO_SRC=$ODOO_HOME/odoo`, `EXTRA_ADDONS=$ODOO_HOME/extra`, `VENV=$ODOO_HOME/venv`, `PGUSER_ODOO=odoo`, `PGPASS_ODOO=odoo`.

## 2. Ejecutar todo con un comando

```bash
tools/steps_app_demo/run_demo.sh
```

Hace, en orden: (1) recrea la base `demo` e instala `step_mobile_portal`, `step_mobile_portal_colaciones`, `step_mobile_portal_mobilization` y `step_mobile_portal_tracker`;
(2) siembra datos sintéticos (`tools/steps_app_demo/seed.py`); (3) levanta Odoo en `:8070`; (4) ejecuta el recorrido de aceptación `mobile/e2e/journey.e2e.test.ts` con el **mismo código de cliente de la app**;
(5) escribe usuarios y contraseña de la demostración en `$ODOO_HOME/demo-summary.json` (**fuera del repositorio**). La contraseña de demostración sale de `DEMO_PASSWORD` o se genera al azar.

Resultado esperado: `Tests 8 passed (8)`.

## 3. Datos sembrados

| Quién | Cuenta (`@demo.steps.test`) | Qué tiene |
| --- | --- | --- |
| Administrador Norte / Sur | `admin.norte`, `admin.sur` (usuarios de Odoo) | Administran accesos solo de su empresa y consultan Colaciones/Movilización de su empresa. |
| Usuario sin acceso | `sin.acceso` (usuario de Odoo) | Sin grupos de Steps: Odoo le niega todo. |
| Beneficiaria de Colaciones | `beneficiaria` | Norte · rol *persona* · vinculada al trabajador «Beneficiaria Demo». |
| Operador de entregas | `operador` | Norte · rol *operador* · **solo el tótem 1** (el tótem 2 existe y está fuera de su alcance). |
| Conductores | `conductor1`, `conductor2` | Norte · rol *conductor* · cada uno vinculado a su chofer y con **un servicio distinto**. |
| Supervisor | `supervisor` | Norte · rol *supervisor* de Movilización. |
| Persona multi-módulo | `multi` | Norte: Colaciones (persona) + Tracker · Sur: conductor con un servicio. Sirve para cambiar de empresa. |
| Cuenta sin empresa | `sinmembresia` | Registrada, sin membresía: no ve nada. |
| Solicitud pendiente | `solicita` | Pidió acceso a Norte; el administrador la aprueba. |
| Invitación | `nuevo` (aún no existe) | Código de invitación (impreso por el sembrado en el resumen) para Norte con rol beneficiaria. |

Dos empresas («Agrícola Demo Norte» y «Agrícola Demo Sur»), con tótems, trabajadores con código, vehículo, recorrido con paradas y servicios.

## 4. Recorrido manual paso a paso (resultado esperado y cómo comprobarlo en Odoo)

Con Odoo en `:8070` y la app en el navegador: `cd mobile && VITE_STEPS_API_BASE=/steps_app/v1 npm run dev` (el servidor de desarrollo reenvía `/steps_app` a Odoo; `STEPS_DEV_ODOO` cambia el destino).

1. **Registro e invitación.** En «Crear cuenta» regístrate como `nuevo@demo.steps.test`. Verás «todavía no tienes acceso a una empresa» y ningún módulo. *Odoo → Steps App → Personas*: aparece sin empresa. Para aceptar la invitación el correo debe estar verificado: como no hay correo saliente en la demo, un administrador **del sistema** lo marca (*Personas → Identidades → «Marcar correo verificado»*, queda en la auditoría). Luego escribe el código de invitación: la portada muestra solo **Colaciones**.
2. **Administración.** Entra a Odoo como `admin.norte@demo.steps.test`: *Steps App → Accesos* (filtro «Solicitudes») muestra a `solicita`. Botón **Asignar módulos y roles** → elige un rol → «Asignar»: la membresía queda activa y con su concesión en un solo paso. `admin.sur` no ve esa fila; `sin.acceso` recibe error de acceso. *Auditoría* lista cada cambio.
3. **Sesión y catálogo.** Inicia sesión en la app como `solicita`: ve solo lo asignado.
4. **Operación sin señal (Colaciones).** Como `operador`: *Colaciones → Registrar entrega*, corta la red (modo avión o `DevTools → Offline`), escribe el código `NEMP1`, «Registrar»: aparece **Guardado en el teléfono** y el estado **Pendiente**. Vuelve la señal: pasa a **Confirmada** con el nombre del trabajador.
5. **Una sola vez en Odoo.** *Colaciones → Registros*: exactamente un registro, con «Operador (app Steps)». Reenviar o pulsar dos veces no crea otro. Como `admin.sur` ese registro no existe.
6. **La persona y el supervisor comprueban.** `beneficiaria` abre *Colaciones*: «Hoy ya recibiste tu colación». En Movilización, `conductor1` abre su servicio, **Inicia**, marca pasajeros (códigos `NEMP3`, `NEMP4`; también puede **Corregir** una marca o **Reportar una incidencia**) y **Finaliza**; `supervisor` ve el servicio, los pasajeros y quién marcó cada uno. *Odoo → Movilización*: cada evento muestra la persona autora; una marca corregida queda **anulada**, no borrada.
7. **Revocación.** Como `admin.norte`, abre la membresía del operador → *Concesiones* → revoca (o «Suspender»). En el teléfono, al revalidar (volver a primer plano o «Revisar de nuevo») el módulo desaparece y la API responde 403. Lo capturado **antes** de la revocación y aún pendiente se acepta; lo capturado después se rechaza con su motivo y queda en *Sincronización*.
8. **Cuenta y empresa.** Entra como `multi`: elige empresa. Con operaciones pendientes en Sur, cambia a Norte: la cola de Sur sigue intacta y no se mezcla. Cierra sesión y entra con otra cuenta en el mismo teléfono: *Sincronización* muestra «datos de otra cuenta», que no se envían ni se borran.
9. **Recuperación.** «Recuperar»: con correo saliente configurado el código llega por correo; en la demo lo emite un administrador del sistema (*Identidades → «Código de recuperación»*). Tras cambiar la contraseña se cierran **todas** las sesiones (también las de un teléfono perdido).

## 5. Solo interfaz (sin Odoo): modo demostración

`cd mobile && npm run demo` abre la app contra un servidor falso con datos ficticios, con una franja roja permanente «MODO DEMOSTRACIÓN». Escenarios con `?scenario=`:
`nuevo`, `conductor`, `beneficiaria`, `pendientes` (sin señal, con una operación rechazada), `multiempresa`, `supervisor`, `sin-modulos`. Contraseña ficticia: `demo-clave-2026`.
Este modo **no** prueba integración: sirve para el trabajo visual. No existe en las compilaciones normales.

## 6. Pruebas automáticas (qué se ejecuta y dónde)

| Capa | Comando | Qué cubre |
| --- | --- | --- |
| Núcleo puro (Python) | `python -m pytest -q tools/tests` | Tokens, contraseñas, vigencias, política de eventos, verificador de Google. |
| Odoo (Odoo 18 real) | `odoo-bin -d <base_test> -i step_mobile_portal,step_mobile_portal_colaciones,step_mobile_portal_mobilization --test-tags /step_mobile_portal,/step_mobile_portal_colaciones,/step_mobile_portal_mobilization --stop-after-init` | Modelos, reglas por empresa **con usuarios reales no superusuario**, API HTTP, política de revocación, módulos deshabilitados. |
| Cliente | `cd mobile && npm test && npm run build` | Sesión, cola durable, sincronización, migración, pantallas (jsdom), escenarios. |
| Extremo a extremo | `tools/steps_app_demo/run_demo.sh` | Cliente real ↔ Odoo real. |
