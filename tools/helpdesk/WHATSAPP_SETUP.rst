WhatsApp para soporte — T48
==========================

Estado de la entrega del 06-10-2026
---------------------------------

El módulo propio ``step_helpdesk_whatsapp`` está instalado en Desarrollo y
Steps. El mismo paquete pasó pruebas en copias de ambos destinos. En Steps se
preparó el canal «Soporte WhatsApp — T48», con el equipo y empresa del ticket,
deshabilitado y con los envíos pausados. No se registró ni migró ningún número
y no se contactó a Meta. El administrador puede abrirlo en:

https://stepsapp.cl/odoo/action-1321/1

También se encuentra en Asistencia / Canales WhatsApp. Ese menú requiere
permisos de administrador; no habilitarlo a todos los usuarios para resolver
un problema de acceso. Los agentes usan Mensajes WhatsApp, WhatsApp por
clasificar y el botón Responder por WhatsApp del ticket.

Pasos para completar la conexión
--------------------------------

1. Iniciar sesión personalmente en Meta Developers. Actualmente solo se
   dispone de WhatsApp Business en el teléfono, sin activos Cloud API.
2. Configurar la aplicación empresarial de Meta, el portafolio y la cuenta
   WhatsApp Business (WABA). Obtener App ID, WABA ID y Phone Number ID desde
   los activos reales. Primero puede usarse el número de prueba de Meta.
3. Antes de registrar el número que ya funciona en el teléfono, comprobar
   en la cuenta la opción y elegibilidad de coexistencia. Esta entrega no
   implementa Embedded Signup ni sincronización del historial del teléfono.
   No eliminar la cuenta del teléfono para forzar el registro. Si la opción
   no está disponible, resolver la incorporación con un proveedor admitido
   o elegir explícitamente otro número para soporte.
4. Crear un token de usuario de sistema asociado a los activos correspondientes,
   con ``whatsapp_business_messaging`` y ``whatsapp_business_management``.
   El token temporal del panel sirve para pruebas y no para una conexión estable.
5. En el canal de Steps completar los tres IDs, la versión Graph API soportada
   que indique Meta, token de acceso y secreto de la aplicación. Ingresarlos
   directamente en los campos protegidos del formulario; no enviarlos por chat,
   tickets, capturas ni Git. El token de verificación ya se genera en el canal.
6. Mantener «Pausar envíos» activo y «Confirmar recepción» desactivado. Guardar
   los datos y habilitar el canal. Copiar su URL de callback y token de
   verificación al webhook de la aplicación Meta, validar y suscribir el campo
   ``messages`` y la aplicación a la WABA. El callback solo acepta un canal
   habilitado y eventos firmados para esa cuenta y número.
7. Desde un teléfono de prueba autorizado, enviar texto, una imagen, un PDF y
   un audio. Comprobar ticket, adjuntos privados, equipo/empresa y respuesta
   humana en el chatter. Verificar que un reenvío del mismo evento no duplica
   el caso y que dos casos abiertos requieren clasificación cuando no hay
   referencia inequívoca. El audio se conserva; no hay transcripción automática.
8. Quitar «Pausar envíos» para una respuesta de prueba explícita desde el ticket.
   Comprobar recepción y estado del mensaje. Después sincronizar las plantillas
   aprobadas. Fuera de 24 horas se exige plantilla y consentimiento registrado.
   Solo después de estas comprobaciones comunicar que la conexión está activa.

Operación y pausa
-----------------

«Pausar envíos» conserva la recepción y bloquea las salidas en cola. Deshabilitar
el canal detiene la aceptación del webhook y el procesamiento de sus entradas
pendientes. Los eventos y mensajes no se borran al pausar. La cola se procesa
cada minuto. Un envío con resultado incierto no se reenvía automáticamente:
soporte debe conciliarlo antes de volver a responder. Las entradas fallidas se
reintentan desde Cola de eventos WhatsApp. Revisar permisos del equipo privado
y empresa antes de incorporar agentes.

El conector no invoca IA, no envía campañas y no usa sesiones WhatsApp Web/QR.
Los acuses automáticos quedan apagados hasta decidir su uso. La integración de
Claude lee ``mail.message.step_wa_inbound`` para reconocer respuestas humanas
aunque todavía no haya un contacto identificado. Los estados de entrega no
se consideran respuestas ni aceptación del cliente.

Decisión y pruebas
------------------

Se eligió un conector propio porque el módulo estándar disponible no ofrece
esta cola persistente de soporte con procesamiento separado del webhook,
asignación explícita de casos y conciliación de envíos inciertos. No se copió
código del proveedor ni se instaló el módulo estándar WhatsApp en paralelo.

El compañero ``step_project_agriculture_scope`` mantiene las relaciones
agrícolas existentes y exige variedad/grupo cuando el centro tiene especie;
permite tareas generales de soporte sin cultivos. Evita que la instalación
nativa de Helpdesk imponga variedades ficticias a tareas generales.

Paquete probado: commit ``86098e8a2d7fbd3231bf7563ca37d83aa9337065``, SHA-256
``e34d760de5ea2ad556c71ed1c831806e429612e95d8d1c650eecda0e2f39b8b5``.
Por destino: 25 pruebas de WhatsApp y 2 del alcance agrícola, sin fallos.
Incluyen webhook firmado, deduplicación, reglas de empresa/equipo, ventana de
respuesta, adjuntos, clasificación, colas y transporte simulado. Las pruebas
simuladas no sustituyen la aceptación con la cuenta y teléfonos reales.

Referencias de Meta
------------------

Colección oficial Cloud API y activos/token:
https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api

Suscripción del webhook:
https://www.postman.com/meta/whatsapp-business-platform/folder/ozgs3jn/webhook-subscriptions

La guía de coexistencia de Meta requiere comprobar el flujo de la cuenta:
https://developers.facebook.com/docs/whatsapp/embedded-signup/custom-flows/onboarding-business-app-users
Su contenido no estuvo disponible mediante la consulta automatizada (HTTP 429);
no se certificó la elegibilidad ni se ejecutó ese proceso.
