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
