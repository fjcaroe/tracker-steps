# Steps App unificada — estado real (actualizado 04-10-2026, segunda sesión)

**Actualización Android del 09-10-2026:** cliente con escáner nativo y API 36,
paquetes APK/AAB compilados y firmados localmente, arranque Android comprobado.
Portal 18.0.1.0.2 instalado en Desarrollo después de 60 pruebas en copia y
comprobación de los registros existentes. Menú y formulario real de accesos
abiertos con el administrador vigente. La publicación interna y la evidencia
final se detallan en [STEPS_APP_ANDROID_PILOTO.md](STEPS_APP_ANDROID_PILOTO.md).
Las limitaciones nativas históricas de abajo ya no describen este piloto.

**Actualización iOS/Apple Watch del 09-10-2026:** primera beta de demostración y
acompañante SwiftUI implementados en la [PR #19](https://github.com/fjcaroe/tracker-steps/pull/19).
iPhone y Watch compilaron con Xcode 26.6, incluidos el archivo de dispositivo
sin firma y el paquete para simulador. La entrega inicial no validó el arranque por una migración del simulador;
la continuación Mac aprobó la instalación/apertura del piloto de Desarrollo en
simulador con Xcode 26.6 ([37989604975](https://github.com/fjcaroe/tracker-steps/actions/runs/37989604975)).
Firma, instalación en equipos reales e ingreso/sincronización física siguen pendientes. La matriz histórica de abajo no certifica esta beta en terreno.
Ver [STEPS_APP_IOS_WATCH_BETA.md](STEPS_APP_IOS_WATCH_BETA.md) para evidencia,
instalación y límites; Tracker en demostración usa una simulación aislada.

**Preparación Mac del 09-10-2026:** 171 pruebas del cliente, builds normal/piloto,
7 comprobaciones HTTPS, 52 pruebas backend Tracker y 22 de herramientas aprobadas
localmente. `ios:pilot` corregido para conservar el aviso. El Mac 2017 no admite
oficialmente Xcode 26; firma y pruebas físicas se continuarán en otro Mac.
La sincronización nativa local terminó con error por Xcode ausente. En macOS
hospedado pasaron compilación iPhone/Watch para simulador, archivo de dispositivo
sin firma e instalación/arranque del piloto (código `164d1c8`, 2.0.0 (9)).
Ver [STEPS_APP_IOS_MAC.md](STEPS_APP_IOS_MAC.md).

Rama de integración: **`codex/steps-movil`** (publicada) · PR draft [fjcaroe/tracker-steps#16](https://github.com/fjcaroe/tracker-steps/pull/16) hacia `develop` (la PR #15 queda reemplazada por esta rama; no se cerró). Todo lo de abajo distingue lo **comprobado**, lo pendiente de validación y lo bloqueado.

## 1. Diagnóstico al comenzar esta sesión (lo que dijo la entrega anterior vs la realidad)

| Afirmación de la entrega anterior | Estado real al comprobar | Evidencia |
| --- | --- | --- |
| Etapa 0: inventario, ADR, matriz, plan de migración | **Solo documentada**, correcta pero sin código que la sostuviera aún | `STEPS_APP_INVENTARIO_Y_ADR.md` |
| Corrección de los 3 hallazgos de la PR #15 | **Implementada y comprobada** desde el primer momento con regresiones; ahora además con el reproductor oficial: fallan en el head `8797edb` y quedan corregidos | `162c3cf`, `docs/evidence/PR15_REGRESIONES.md`, `tools/reviews/pr15_repro.cjs` |
| Etapa 1: módulo Odoo `step_mobile_portal` | **Implementada, pero NO había sido ejecutada** (no había Odoo). Al ejecutarla contra Odoo 18 real aparecieron **5 defectos** (fechas vacías = `False`, token de Google mal formado provocaba una petición de red, pruebas que revertían escrituras, `url_open`…) | commit `df51694` |
| Etapa 2: Colaciones y Movilización con cola offline | **Implementada, comprobada solo contra un servidor falso**. Al integrarla con Odoo real apareció un defecto **serio**: un envío en curso usaba la empresa/cuenta *actual* y no la de su cola | commit `72616b0` |
| Documentación, contrato visual, cierre Git | **Parcial**: sin demostración reproducible, sin guía, sin Odoo ejecutado | este documento y `STEPS_APP_DEMO.md` |

Conclusión: la base era correcta en diseño pero **no comprobada de extremo a extremo**; esta sesión la ejecutó contra Odoo real y corrigió lo que falló.

## 2. Matriz de estado

Leyenda: ✅ comprobada · 🟡 implementada, pendiente de validación · 🔶 parcial · 📄 solo documentada · ⛔ bloqueada por dependencia externa.

| Capacidad | Estado | Dónde / evidencia |
| --- | --- | --- |
| Núcleo Odoo: personas, identidades, membresías, concesiones, invitaciones, dispositivos, sesiones, auditoría | ✅ | `step_mobile_portal/`; 37 pruebas en Odoo 18 real |
| Administración (asistente «Asignar módulos y roles», filtros, dispositivos, sesiones, identidades, vencimiento de invitaciones, verificación manual, código de recuperación) | ✅ | vistas validadas por Odoo al instalar; `tests/test_admin.py`; recorrido E2E pasos 1-2 |
| Reglas por empresa con **usuarios reales** (admin de otra empresa, consulta, sin permisos) | ✅ | `test_admin.py` (15 casos) y E2E con `admin.norte`/`admin.sur`/`sin.acceso` |
| Registro, ingreso, bloqueo por intentos, renovación rotatoria con detección de reutilización, cierre de sesión | ✅ | `test_portal.py`, `session.test.ts`, E2E |
| Recuperación de acceso / teléfono perdido (código → contraseña nueva → todas las sesiones cerradas) y revocación de dispositivo (por el dueño o el administrador de su empresa) | ✅ | `TestRecovery`, E2E «Recuperación…», `App.test.tsx` |
| Verificación de correo | 🔶 | El código solo viaja por correo (`step_app.send_mail=1`); sin correo saliente lo marca un administrador del sistema (auditado). No se probó un envío de correo real. |
| Google | ⛔ | Verificador de servidor listo y probado (firma/emisor/audiencia/expiración, sin red ante basura); faltan ID de cliente OAuth y plugin nativo. El botón no aparece. |
| Apple | ⛔📄 | No implementado (guía 4.8). |
| Catálogo de módulos real (autorización del servidor; módulo deshabilitado corta endpoints y eventos; contrato incompatible → mensaje; módulo desconocido ignorado; respuesta atrasada descartada) | ✅ | `session.test.ts`, bridges `test_*_app.py`, E2E |
| Colaciones: persona (habilitación e historial propios) y operador (alcance por tótem), duplicados, doble pulsación, no habilitado, tótem archivado, rechazo conservado, revocación | ✅ | `test_colaciones_app.py` (9), `journeys.test.ts`, E2E pasos 3-9 |
| Colaciones: reservas/solicitudes | 📄 | **No existen en el dominio** (su «plan» es semanal por departamento). No se inventaron. |
| Colaciones en modo compartido/tótem (emparejamiento propio) | 📄 | Un dispositivo `shared` se rechaza (`shared_device_pairing_required`); el tótem actual sigue con su token y su PWA. Pendiente de diseño. |
| Movilización: servicios propios, detalle con paradas, abrir/cerrar, marcas por código, corrección de marcas (anular), incidencias, supervisor, autoría, identidad no suplantable | ✅ | `test_mobilization_app.py` (13), `journeys.test.ts`, E2E |
| Movilización: lista previa de pasajeros autorizados por servicio | 📄 | El dominio no la tiene: se valida en servidor contra empleados activos de la empresa. |
| Movilización: GPS de ruta en segundo plano | 📄 | No implementado ni afirmado. Posición puntual al marcar, con permiso denegado manejado. |
| Cola durable: persistir antes de anunciar, estados, aislamiento por persona/empresa/módulo, idempotencia, orden por grupo, rechazo no bloquea a otros, no borra por límite/sesión/cuenta | ✅ | `sync.test.ts`, `hardening.test.ts`, `journeys.test.ts` |
| Reintentos con espera progresiva y tope («detenida»), «Reintentar» = intento real, bloqueo por almacenamiento, un solo proceso enviando | ✅ | `hardening.test.ts` |
| Carreras de cambio de empresa/cuenta durante un envío o una consulta | ✅ | `session.test.ts` (fallan sin el arreglo; verificado), E2E paso 10 |
| Tracker integrado como módulo con sus datos; compuerta de propietario; copia de seguridad verificada; recuperación | ✅ (lógica) / 🟡 (instalación real) | `owner.test.ts`, `migrations.test.ts`, suite previa del Tracker. **No** se probó una actualización real sobre un teléfono con jornadas. |
| Unir persona ↔ usuario Tracker (SSO) | 📄 | Pendiente de decisión de datos (ADR-6): hoy el Tracker conserva su login. |
| Lectura de códigos con cámara | 🟡 | `platform/scanner.ts` (API web `BarcodeDetector`), probada con simulación; **sin validar en dispositivo**; la alternativa (teclear/lector) siempre existe. |
| Interfaz completa (bienvenida, registro, recuperar, incorporación, empresa, inicio, Colaciones, Movilización, Tracker, perfil/dispositivos, sincronización) con carga/vacío/error/permiso/offline | ✅ (web) | `App.test.tsx`, `demo.test.tsx` |
| Modo demostración con 7 escenarios ficticios | ✅ | `npm run demo`, `testing/demo.ts` |
| Demostración reproducible contra Odoo real | ✅ | `tools/steps_app_demo/run_demo.sh`; `STEPS_APP_DEMO.md` |
| Android: compilar/ejecutar | ⛔ | Sin SDK y `dl.google.com` inalcanzable. Instrucciones en `STEPS_APP_NATIVE.md`. |
| iOS: compilar/ejecutar | ⛔ | Requiere macOS/Xcode. |
| Almacén seguro nativo, HTTP nativo, segundo plano, permisos en dispositivo | 🟡 | Código y simulación; sin dispositivo. |

## 3. Pruebas ejecutadas en esta sesión

| Qué | Resultado |
| --- | --- |
| Odoo 18 real, base nueva, instalando los 4 addons: `--test-tags /step_mobile_portal,/step_mobile_portal_colaciones,/step_mobile_portal_mobilization` | **59 pruebas, 0 fallos** (37 portal + 9 Colaciones + 13 Movilización) |
| Recorrido E2E cliente real ↔ Odoo real (`run_demo.sh`) | **8 pasos aprobados**, repetido desde base nueva varias veces |
| `cd mobile && npm test` | **156 pruebas, 15 archivos, aprobadas**; `npm run build` correcto |
| `python -m pytest -q tools/tests` | **22 aprobadas** |
| Reproductor PR #15 | Falla en `8797edb`, correcto en la rama (ver evidencia) |
| `npx cap sync android/ios`, `npx cap doctor` | Correctos / Xcode ausente |
| **No ejecutado:** `backend/tracker_py` (dependencias no instaladas aquí; sin cambios en backend), Android/iOS, cualquier prueba en dispositivo |

El Odoo usado es 18.0 (rama `18.0` de `odoo/odoo`) con PostgreSQL 16 local, **fuera del repositorio** (`/opt/odoo-env`), más `step_mobilization` de `origin/develop` como dependencia.

## 4. Defectos reales encontrados al ejecutar (y corregidos)

1. Odoo entrega fechas vacías como `False` y el núcleo comparaba con `None` → `TypeError` en vigencias.
2. Un token de Google mal formado provocaba una petición de red a Google (latencia/DoS) → se descarta localmente.
3. Deshabilitar un módulo en Odoo no cortaba el registro de eventos capturados antes (las concesiones seguían en la historia).
4. **El contador de pasajeros del módulo base no se recalculaba al anular una marca** (`step_mobilization`): se redeclaró la dependencia en el puente. Conviene llevarla al módulo base.
5. **Un envío en curso se hacía con la empresa o la cuenta *actuales***, no las de su cola: podía rechazar como «no encontrado» una operación legítima o mezclar empresas. Corregido con APIs acotadas a persona+empresa y descarte de respuestas atrasadas.
6. Un arranque doble de la sesión reiniciaba el estado visible.

## 5. Integración y ramas

- **Integrado:** PR #15 (corregida), módulo Odoo + 3 puentes, cliente unificado con Tracker como módulo, demostración y documentación, todo en `codex/steps-movil` (commits `162c3cf` … `b30bda3` y los de cierre de esta sesión).
- `step_mobilization` (solo en `develop`/`codex/cierre-cambios-locales`) **no se copió**: es dependencia declarada del puente.
- Web Tracker (`codex/web-tracker-redesign`) no se tocó. **Nada se desplegó** ni se publicó en tiendas; el piloto no sustituye ninguna instalación vigente.

## 6. Pendiente y bloqueos

Ver `STEPS_APP_NATIVE.md §4` (lanzamiento), y: correo saliente real; Google/Apple; SQLite/IndexedDB antes de añadir GPS continuo; modo compartido de tótem; SSO con el usuario Tracker; limitación de tasa por IP; validar la actualización real sobre instalaciones con datos; llevar al módulo base la dependencia del contador.
