# Asociación de una unidad física durante instalación

El usuario confirma IMEI o su terminación ya identificada, patente y propietario.
Los datos reales de matrícula, chasis, motor y SIM se guardan exclusivamente en
planes/recibos privados; nunca en el repositorio público.

`tools/gps/prepare_vehicle_installation.py` utiliza el inventario y las API
existentes. Rechaza una SIM diferente, patente duplicada, compañía distinta o
unidad asociada a otro vehículo. Toma respaldo y bloqueo compartido, reutiliza
un activo por patente o crea el vehículo real confirmado, y asocia la unidad
mediante versión y validaciones del servidor. No envía SMS ni controles físicos.

Una asociación nueva inicia un diagnóstico de instalación en modo captura.
Las observaciones del banco de pruebas quedan en el recibo/inbox, sin usarlas
como historial del vehículo recién instalado. No se activa seguimiento con una
posición anterior a la asociación. El indicador revisado solo permite promover
una posición GPS válida y reciente que satisfaga los controles de la API. Si
todavía conectan la alimentación, la entrega queda asociada y esperando una
nueva señal; no se presenta como ubicación en vivo ni se programa una aprobación
automática sin revisión.

`install_native_vehicle.py` reutiliza marca/modelo por coincidencia normalizada,
incluidos registros archivados, y comprueba patente/VIN para evitar duplicados.
La compañía se verifica contra el RUT legal informado. Conserva los campos
nativos de modelo, matrícula, año, color y chasis y crea el enlace explícito al
activo existente. Motor, procedencia, fabricante y dígito verificador se
conservan en la descripción cuando no existe un campo nativo específico. No se
usa el país de matrícula como procedencia ni se crean campos Studio. No se
inventa conductor, lectura de odómetro, costos o documentos financieros.

`manage_vehicle_installation.py` ensaya dos veces el mismo registro y enlace en
una copia fresca neutralizada del destino, con búsqueda remota simulada solo
en la copia. Certifica idempotencia, guarda el hash de los hechos privados y
exige el mismo commit/datos antes de aplicarlos. La publicación de datos toma
otro respaldo y bloqueo. No despliega módulos, frontends, receptor ni código
de la API. La capacitación de QA-Cerro no recibe registros reales ni se refresca.

Validación con la cuenta existente: `vehicle-installation-native.cjs` comprueba
la selección de compañía, asociación en el formulario GPS/SIM, ficha nativa,
chasis y presencia en la app móvil. No crea jornadas ni envía comandos. Las
sesiones de revisión se eliminan al terminar. La ausencia de primera posición
se informa expresamente y no impide registrar correctamente la ficha.

Entrega del 02-11-2026: primera unidad del cliente asociada y ficha nativa
comprobada. El instalador confirmó que aún estaba conectando la alimentación;
al entregar permanecía en captura y sin primera posición del vehículo.
Paquete probado `4c01f9f72dd06c43d7d9bdefb8edea464d0eab0e`. Evidencia privada:
`/opt/steps-validation/cerro-first-install-20261102/`,
`/opt/steps-validation/vehicle-installation-native-20261102/` y
`~/.codex/local-artifacts/cerro-first-install-20261102/`.

Revisión posterior: al confirmar el cliente que ya vio la unidad, se comprobó
una posición TCP reciente posterior a la asociación, identidad y ubicación de
la instalación. Se activó `forward` por la API versionada, con respaldo y
bloqueo, y se comprobó su propagación al receptor. Las observaciones de captura
no se convierten retrospectivamente en historial: la primera posición de
seguimiento requiere una transmisión nueva. El verificador admite
`REQUIRE_APPROVED=1` para comprobar la aprobación en web/móvil y
`REQUIRE_LIVE=1` para exigir además esa primera posición real. No confundir
ambas comprobaciones. Evidencia privada de activación:
`/opt/steps-validation/cerro-first-live-20261102/`.

`installation-native-session.py` permite la revisión con el usuario y compañía
existentes, comprueba el enlace nativo y genera una sesión efímera; se retira
con `cleanup_personal_sessions.py`. No cambia contraseñas ni membresías.

Cuando se identifica al conductor, `driver_login` y `driver_user_id` deben
coincidir con una cuenta interna activa de la compañía. Se reutiliza su contacto
en `fleet.vehicle.driver_id`: las reglas nativas pueden impedir leer una ficha
sin ese conductor, aunque Tracker ya tenga el UUID autorizado. Se completa el
dato real, sin ampliar la regla para eludirlo. Un conductor existente diferente
detiene el registro para evitar reemplazar otra asignación silenciosamente.

`configure_user` asigna el vehículo real y el grupo de operación individual,
habilita el control de arranque para ese usuario y conserva sus grupos anteriores.
Comprueba que los perfiles de los otros usuarios no cambien. Sin esa opción,
completar el conductor no cambia permisos. La repetición sobre copia fresca
verifica la idempotencia; el commit emite la señal nativa de invalidación de
caché para los procesos web. No se modifica ninguna contraseña.

`vehicle-owner-review.cjs` revisa la cuenta real en formato de teléfono, la ficha
nativa, datos técnicos y conductor, protección y relé, y el rechazo de otro
vehículo de la misma compañía (posiciones, control físico y costos incluidos).
Las sesiones son efímeras y no se emiten órdenes físicas. Matrícula, motor,
chasis, SIM y cuentas se conservan exclusivamente en hechos privados.

Segunda instalación del 02-11-2026: se reutilizó el activo que había vinculado el
usuario y se registró su vehículo y conductor con acceso individual. Se ensayó
dos veces en una copia fresca y se publicó el mismo paquete con respaldo y
bloqueo. La revisión cruzada detectó el conductor ausente de la primera ficha;
se completó tras otro ensayo en copia, sin cambiar sus permisos. Ambas cuentas
acceden únicamente a su vehículo y rechazan el otro. Los relés quedan registrados
para la prueba supervisada; no se afirma un resultado físico sin comprobarlo.
No hay cambios de módulos, frontend o API ni copia de datos a QA-Cerro.
Paquete operativo: `354614a4e75fec5c592b8b74d860de2405854b8d`.
Evidencia privada: `/opt/steps-validation/cerro-second-vehicle-20261102/` y
`~/.codex/local-artifacts/cerro-second-vehicle-20261102/`.
