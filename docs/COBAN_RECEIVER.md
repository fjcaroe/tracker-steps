# Receptor Coban para Cerro - 31/10/2026

Solicitud explícita del usuario: preparar y habilitar hoy el receptor para
Cerro El Plomo productivo; los cuatro IMEI, números SIM y manual llegarán aparte.

Paquete independiente en receivers/coban, sin reemplazar Teltonika, API,
frontend ni addons Odoo. Destino reservado: IP estática de odoo-new,
35.222.25.110, TCP 5001. No usar UDP ni 5027 para este receptor.
La apertura externa solo queda confirmada tras publicar y probar firewall.

## Alcance de protocolo

GPS103 ASCII con login `##,imei:...,A` / LOAD, heartbeat IMEI / ON,
posición F válida terminada en punto y coma, y variante decimal ALT terminada
en asterisco. Parser independiente contrastado con el proyecto Traccar:
https://github.com/traccar/traccar/blob/master/src/main/java/org/traccar/protocol/Gps103ProtocolDecoder.java

Las coordenadas F se convierten de grados/minutos y sus velocidades de nudos
a km/h; ALT utiliza grados decimales y km/h. Solo datos GPS válidos; LBS y
posiciones inválidas no fabrican puntos. El reloj del dispositivo debe usar UTC.
Una fecha futura o inválida queda rechazada, con captura privada solo para IMEI
permitidos. Un indicador de carga de batería no se convierte en corte de energía.

No se afirma compatibilidad física con una revisión 401C hasta recibir su manual
y una trama real. No se implementan variantes binarias, GT06, fotos, comandos
de configuración ni control de motor. La única respuesta de alarma es el acuse
de recibo SOS del protocolo, después de persistir el evento.

## Registro privado y encaminamiento

/etc/steps-coban/devices.json contiene solo los IMEI autorizados. Vacío inicialmente.
Cada entrada tiene issuer CERRO_EL_PLOMO, company_id, mode y, para forward,
device_id UUID del inventario existente. Mode capture conserva hasta 200 tramas
privadas para validar la unidad sin crear posiciones en la aplicación. Mode
forward requiere además alta y asociación del vehículo en Tracker.

No incluir IMEI, teléfonos, tramas reales ni contraseñas en Git, pruebas públicas
o logs. El protocolo identifica por IMEI, sin autenticación criptográfica del
aparato; la lista restringe la recepción pero no convierte el protocolo en TLS.
La clave de puente de Cerro vive en archivo privado root:steps-coban 0640;
no se imprime ni se modifica la clave compartida original.

SQLite WAL/FULL conserva la cola antes del reenvío. SHA-256 del mensaje identifica
duplicados; recibos de la API completan la entrega, con reintentos y backoff.
La ruta de cada evento queda congelada; cambiar el mapa no mueve eventos a otra
compañía. La API existente valida nuevamente tenant y asignación para la fecha.
Retención de recibos siete días, cola pendiente máxima 20.000, capturas 200,
tramas 4 KiB, buffers 16 KiB, 64 conexiones globales y 8 por IP, 120 mensajes/min
por conexión. Capturas/estado son privados y no se registran payloads en journal.

## QA y publicación

tools/ops/deploy_coban.py valida SHA-256 y commit del paquete, toma el bloqueo
/run/lock/steps-environments.lock y ensaya el mismo código en el entorno privado
de validación: copia fresca del destino tracker_steps, dump decodificado, tests
unitarios y flujo TCP real hacia la API actual sobre esa copia. Se comprueban
consulta de flota, reinicio durable, deduplicación y rechazo entre compañías.
Se comparan datos GPS reales y fuentes de API antes/después; no se cambian.

La publicación instala un servicio no privilegiado steps-coban, código bajo
/opt/steps-coban/releases/<commit>, enlace current, configuración y datos privados.
No sobrescribe raíces existentes. Crea únicamente una regla GCP TCP 5001 con
tag steps-coban-cerro para esa VM. Conserva el resto de tags y reglas. El respaldo
de configuración previa queda en /opt/steps-validation/coban-receiver-20261031/.
No hay migración ni reinicio de Odoo, API, nginx o Teltonika.

## Al recibir los cuatro equipos

1. Registrar IMEI/SIM/vehículo/sociedad en inventario privado y en Tracker.
2. Cotejar manual y sintaxis, activar lista en mode capture con la sociedad real.
3. Confirmar login, heartbeat y trama GPS; comprobar interpretación y hora.
4. Asociar el device UUID al vehículo existente y pasar a forward explícitamente.
5. Comprobar posiciones nuevas en Cerro, reconexión tras corte normal y SMS de
   administración. No aprobar seguimiento ni despachar como listo antes de ello.

El mapa se relee por mensaje, sin reiniciar el receptor. Ninguna entrada o
vehículo ficticio se crea en producción para probar este servicio.
