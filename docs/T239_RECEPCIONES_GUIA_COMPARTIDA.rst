Recepciones Excel con una guía compartida
========================================

El importador de Fruta a proceso permite que una guía de productor ampare
varias referencias externas de recepción del mismo fundo. Cada combinación
de referencia y fundo conserva su propio borrador y sus tarjas, kilos,
envases y fecha de recepción.

La versión ``step_packing_ticket_revision`` 18.0.1.2.8 retira el rechazo por
número de guía compartido. Conserva la comprobación de referencia vigente
por empresa, packing, temporada y fundo, así como el rechazo de tarjas
repetidas o reservadas por otra recepción. La importación sigue siendo
atómica y no genera existencias hasta la validación nativa de cada recepción.

El paquete ``reception-excel`` actualiza únicamente este módulo. Se prueba
en copias frescas de Desarrollo, Cerro El Plomo y QA-Cerro, manteniendo los
demás módulos instalados. El caso adjunto se reproduce con el usuario,
empresa y equivalencias del asistente nativo original mediante
``tools/ops/run_external_reception_case.py``. El plan y el Excel se mantienen
fuera del repositorio; la prueba siempre se revierte y solo admite bases
privadas certificadas.

La regresión cubre cuatro referencias y dos guías compartidas del mismo
fundo, ocho tarjas, preservación de cantidades y estado en borrador, ausencia
de cambios de stock, reimportación rechazada y referencias repetidas con
tarjas diferentes. La publicación usa el mismo paquete probado, respaldo,
overlay privado y bloqueo común. Los archivos del cliente se cargan por el
operador después de la actualización; el despliegue no importa recepciones.
