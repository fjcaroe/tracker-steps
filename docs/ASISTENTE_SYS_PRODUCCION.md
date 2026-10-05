# Asistente con IA en SyS producción

Entrega solicitada el 5 de octubre de 2026, hora de Chile: llevar el chatbot
de Demo-SyS a SyS producción, reutilizando explícitamente la misma clave.
La rama canónica del producto es `codex/odoo-support-chatbot`.

| Destino | Base | Servicio | Código | URL |
|---|---|---|---|---|
| Referencia Demo-SyS | `STEPS_DEMO_SYS` | `odoo18-demo-sys.service` | `/opt/demosys_odoo18/odoo_agriculture` | `https://demo-sys.stepsapp.cl` |
| SyS producción | `SyS` | `odoo18-sys.service` | `/opt/luis_odoo18/odoo_agriculture` | `https://sys.stepsapp.cl` |

`produccion` en los scripts existentes sigue significando producción **Steps**
(`karo_consultorias`); el nuevo destino explícito es `sys-produccion`.
Las rutinas históricas de cinco ambientes no agregan SyS automáticamente.

## Código y configuración

Se conserva el código del chatbot de referencia: `step_support_assistant`
versión `18.0.1.1.0`, comparado contra sus 33 archivos públicos. No se copian
usuarios, registros de negocio ni artículos privados de la base demo.
El puente `step_support_assistant_knowledge` se instala únicamente si
Conocimiento ya está instalado en la base destino; SyS no lo tiene instalado.

El proceso de SyS carga el archivo privado existente
`/etc/steps/assistant-demo-sys.env`, propiedad de root y modo 0600, mediante
`/etc/systemd/system/odoo18-sys.service.d/steps-assistant.conf`.
La activación normal no modifica ni duplica el archivo de la clave. Ambos
servicios referencian el mismo archivo; al rotarlo, reiniciar los servicios que lo usan.
La clave no se imprime, no queda en argumentos, base de Odoo, código ni Git.

Se copian exclusivamente cuatro parámetros validados de Demo-SyS:

| Parámetro | Referencia comprobada |
|---|---|
| IA habilitada | `True` |
| Modelo | `gpt-4.1-mini` |
| Límite por usuario/hora | 20 |
| Límite por base/día UTC | 500 |

Los límites locales de cada base son independientes; ambas usan la misma
credencial de OpenAI. Las consultas de registros y saldos se resuelven dentro
de Odoo con ACL, reglas de registros y compañía actual. La generación con IA
usa únicamente ayuda aprobada. Ver [ASISTENTE_ODOO.md](ASISTENTE_ODOO.md).

## Despliegue reproducible

1. Ejecutar como root `tools/chatbot/inspect_sys.py` en `odoo-new` para verificar
   versiones, configuración y presencia de la clave sin imprimirla. Descargar
   el paquete público capturado a `~/.codex/local-artifacts/` y comparar con
   la rama canónica antes de modificar SyS.
2. Registrar y subir los cambios. Generar un paquete fuera del checkout con
   `python tools/chatbot/build_release.py --output RUTA_EXTERNA`; incluye
   únicamente los dos addons. Empaquetar las herramientas con
   `git -c core.autocrlf=false archive` para conservar LF de Bash en Windows.
3. Copiar herramientas y paquete a `/tmp/` de la instancia. Ejecutar:

```bash
sudo -n python3 /tmp/HERRAMIENTAS/tools/chatbot/deploy_sys_production.py \
  /tmp/steps_assistant_sys_release.tar.gz SHA256 COMMIT_PUBLICADO
```

El orquestador exige que el paquete coincida con el código de Demo-SyS,
respalda la configuración de activación y el home de SyS, agrega solamente
la referencia al archivo privado de entorno, y ejecuta el instalador existente
contra `sys-produccion`. El instalador respalda la base y los módulos, instala
solo el asistente y reinicia únicamente SyS. La activación ejecuta consultas
de negocio con el proveedor bloqueado, rechaza acceso público y realiza tres
comprobaciones reales de IA con preguntas genéricas (ayuda, cambio de alcance,
solicitud de secretos). Esas tres comprobaciones consumen tokens; no envían
registros financieros ni valores de producción al proveedor.

Los parámetros de activación se confirman en una sola transacción únicamente
después de pasar las comprobaciones. Si fallan, revisar el error y mantener
la IA deshabilitada mientras se corrige. No se restaura automáticamente la base.
El cierre comprueba clave compartida en los procesos, fuente Demo-SyS intacta,
plantillas y texto del home de SyS intactos, archivos de entrega y acceso HTTP.

### Corrección del formato de la credencial existente

La primera prueba recibió HTTP 401 `invalid_api_key`. Se comprobó sin imprimir
valores que el entorno de Demo-SyS contenía caracteres adicionales alrededor
de una sola credencial completa. Esa credencial ya existente autenticó
correctamente contra OpenAI. `probe_existing_key.py` permite comprobar ese caso
sin guardar respuestas ni consumir tokens de generación.

`repair_key_format.py` admite exclusivamente esa corrección: exige una única
credencial identificable, autenticación HTTP 200, archivo de root modo 0600 y
ausencia de otras variables. Respalda el archivo original con modo 0600 dentro
de un directorio privado 0700, reemplaza atómicamente solo el formato y recarga
los servicios que todavía usen el valor anterior. No crea ni rota una clave.
Demo-SyS se reinició para cargar esa misma clave correctamente; su código y
datos de negocio no se modificaron. El despliegue posterior compara Demo-SyS
contra ese estado corregido.

## Uso y recuperación

Los usuarios internos acceden desde el globo **Ayuda**, abajo a la derecha,
o desde **Ayuda Steps → Consultar al asistente**. Tras instalar, recargar el
navegador para cargar los nuevos assets. **Ayuda Steps → Ajustes** permite
desactivar IA o cambiar límites; las consultas de datos reales siguen disponibles.

La activación guarda evidencia y la versión del override anterior en
`/opt/backups/steps-assistant-sys-activation-FECHA_UTC/`; el instalador guarda
la base y código anterior en `/opt/backups/steps-assistant-sys-produccion-FECHA_UTC/`.
Para desactivar, usar Ajustes. Para retirar únicamente la referencia a la clave,
reponer el override anterior según el respaldo, ejecutar `systemctl daemon-reload`
y reiniciar `odoo18-sys.service`. No eliminar el archivo compartido de la clave:
Demo-SyS lo utiliza. Revisar operaciones posteriores antes de cualquier
restauración de la base completa.

Cerrar con `python tools/git/verify_handoff.py --require-pushed`.

## Resultado verificado — 5 de octubre de 2026, Chile

- Despliegue y activación: commit `556755b9fcb2f1dff0e8725ba114977e757358b8`.
- Paquete de los 33 archivos del chatbot: SHA-256
  `731ca830c196fd1f56f9253b885b4a66947a7d63b1e841dd3a7396766b2a65a6`.
- Respaldo de base y addons:
  `/opt/backups/steps-assistant-sys-produccion-20261005T163210Z`.
- Respaldo de activación y home:
  `/opt/backups/steps-assistant-sys-activation-20261005T163208Z`.
- Respaldo privado previo a corregir el formato de la misma clave:
  `/opt/backups/steps-assistant-key-format-20261005T162823Z`.
- Asistente instalado `18.0.1.1.0`, ocho guías aprobadas disponibles, IA activa,
  modelo `gpt-4.1-mini`, límites 20 por usuario/hora y 500 por base/día.
- Consultas reales verificadas con usuario contable existente y proveedor
  bloqueado: asientos, facturas, pagos, fabricación, tareas y demás catálogos
  disponibles; saldo de cuenta verificado. No se imprimieron valores de negocio.
  Usuarios públicos rechazados. Consultas de datos: cero llamadas de API.
- Tres comprobaciones reales de IA: ayuda `answered` con una cita verificada;
  cambio de tema `out_of_scope`; solicitud de secretos `out_of_scope`.
- Navegador: globo de Ayuda visible y apertura correcta; una cuarta pregunta
  genérica de permisos respondió con la guía y cita correspondientes. En móvil
  de 390 px, documento de 390 px y panel de 366 px, sin desbordamiento horizontal.
- Archivos desplegados coinciden con el paquete; procesos de ambos servicios
  cargan la misma clave. Código/configuración del chatbot de Demo-SyS y home
  de SyS permanecen intactos respecto del estado posterior a corregir el formato.
  Acceso HTTP operativo y SyS reiniciado con la activación confirmada.

Las pruebas iniciales con la credencial mal formada recibieron HTTP 401; la
activación no se confirmó hasta corregir el formato y pasar las verificaciones.
No se creó otra clave, no se rotó la existente y no se restauró la base completa.

## Perfil contable de SyS — 5 de octubre de 2026

La versión `18.0.1.2.0` incorpora ocho guías verificadas sobre asientos/apuntes,
saldos y movimiento del período, facturas/notas de crédito, pagos,
cuentas por cobrar/pagar, bancos/conciliación, flujos de caja y proformas.
Se revisaron los menús de la base SyS y el código de Tesorería antes de redactarlas.
Las guías explican los límites de las consultas y remiten a las pantallas de
Odoo para filtros, informes y acciones que el asistente no ejecuta.

Se activa exclusivamente en SyS el parámetro
`step_support_assistant.guide_profile=accounting`. La biblioteca se titula
**Guías de contabilidad y tesorería**, con las guías contables primero y
ayuda general después. Colaciones conserva sus artículos pero queda fuera
de las fuentes documentales de ese perfil; su consulta de registros sigue
disponible según permisos. La migración clasifica y ordena solo las guías
estándar, preservando textos, aprobación y fuentes propias.

Para repetir esta actualización, generar el paquete y subir herramientas
desde un commit publicado según el procedimiento anterior; ejecutar:

```bash
sudo -n python3 /tmp/HERRAMIENTAS/tools/chatbot/deploy_sys_accounting_guides.py \
  /tmp/steps_assistant_sys_accounting.tar.gz SHA256 COMMIT_PUBLICADO
```

Esta rutina no exige igualar el código de Demo-SyS: SyS recibe una nueva
versión de guías. Respalda metadata del perfil en un directorio privado y usa
el instalador para respaldar base/addons antes de actualizar. Comprueba
archivos, consultas locales sin API y una pregunta genérica de ayuda contable
con cita de la guía nueva; solo esa pregunta consume tokens. No copia registros
ni envía documentos financieros. Mantiene clave, modelo y límites, textos
existentes, home de SyS y versión/configuración/proceso de Demo-SyS.
Para volver al enfoque general usar **Ayuda Steps → Ajustes** y recargar el
navegador. No requiere desactivar IA ni restaurar la base.

Resultado de la actualización:

- Commit desplegado: `cddcb53a71681df060b42587a00afd615a394bf6`.
- Paquete de 35 archivos: SHA-256
  `c2b8db8de712cc0591ac7e42327bb80befe0bcb381dc0714426ee2562bd9a78f`.
- Respaldo de base/addons:
  `/opt/backups/steps-assistant-sys-produccion-20261005T165225Z`.
- Metadata previa del perfil:
  `/opt/backups/steps-assistant-sys-accounting-20261005T165225Z`.
- Versión instalada `18.0.1.2.0`; el usuario contable de verificación ve doce
  guías: ocho contables y cuatro generales. Ninguna de Colaciones.
- Quince pruebas locales y veintiuna pruebas Odoo en base aislada pasaron,
  incluyendo exclusión de fuentes ajenas al perfil en biblioteca/proveedor,
  aislamiento por compañía y preservación de guías propias.
- Pregunta genérica sobre saldo acumulado y fecha Desde: `answered`, dos
  citas verificadas, incluida la guía nueva de saldos. Consultas de asientos,
  facturas y pagos verificadas con proveedor bloqueado: cero llamadas de API.
- Navegador de producción: título contable y orden correcto de las doce
  guías; apertura de la guía de saldos con su texto y clasificación correctos.
  Captura guardada fuera del checkout en `~/.codex/local-artifacts/`.
- Archivos coincidentes con el paquete; clave y cuatro parámetros de IA,
  textos/aprobación de guías anteriores, home y Demo-SyS preservados.
