# T126 — código arancelario de especies

> Actualización posterior al mensaje humano de los cuatro tickets: paquete C
> preparado, prueba privada en cola bajo el bloqueo compartido. Aún sin publicar.

Revisión de las 11:00 del 27-10-2026. Leídos descripción, comentarios y adjunto
3417, incluido el formulario capturado. Pide un campo de texto en `step.especie`
y autoriza Desarrollo, Cerro y QA-Cerro. No pide asignar códigos concretos.

`step_species_tariff` 18.0.1.0.0 extiende el maestro original con `tariff_code`,
etiqueta Código arancelario, texto opcional. Hereda formulario y lista existentes,
preservando IDs, relaciones y permisos. Mantiene ceros iniciales y puntuación;
no precarga ni determina clasificaciones arancelarias.

Paquete preparado: commit `6bfb5994ed67d9af8a6f4824dd1a3fcc113e9858`, SHA256
`bfe60bff12a511873240b1c7e59870e637b2d8303b4eb972dfb927a0eddb514b`.
Archivo remoto `/opt/steps-validation/t126-20261027/species-tariff-B.tar`.
Rama propia compartida con T124/T125: `codex/t124-t125-20261027`.

Hay dos pruebas: texto sin pérdida y edición de una especie existente por el
formulario original sin reemplazarla. El ensayo A pasó la segunda y falló al
crear el fixture de la primera por omitir el grupo de especie obligatorio.
Se corrigió el fixture usando el grupo y alcance de empresas de una especie
existente. La batería B **aún no corrió**: el bloqueo estaba ocupado por otro
ensayo Community. No afirmar QA aprobada ni instalar en producción.

Probe nativo: `tools/ops/verify_species_tariff.py`, con usuario de negocio
existente, menú de especies de Packing, formulario real, mismo maestro y prueba
de escritura en copia con rollback. El tipo `species-tariff` del operador solo
incluye este addon, sin publicar padres ni paquetes Community.

Continuar cuando el bloqueo compartido quede libre:

```text
sudo python3 /opt/steps-validation/t126-20261027/tools/ops/manage_management.py qa development /opt/steps-validation/t126-20261027/species-tariff-B.tar t126b --kind species-tariff
sudo python3 /opt/steps-validation/t126-20261027/tools/ops/manage_management.py deploy development /opt/steps-validation/t126-20261027/species-tariff-B.tar t126b --kind species-tariff
sudo python3 /opt/steps-validation/t126-20261027/tools/ops/manage_management.py compatibility cerro /opt/steps-validation/t126-20261027/species-tariff-B.tar t126c --kind species-tariff
sudo python3 /opt/steps-validation/t126-20261027/tools/ops/manage_management.py deploy cerro /opt/steps-validation/t126-20261027/species-tariff-B.tar t126c --kind species-tariff
sudo python3 /opt/steps-validation/t126-20261027/tools/ops/manage_management.py compatibility qa-cerro /opt/steps-validation/t126-20261027/species-tariff-B.tar t126q --kind species-tariff
sudo python3 /opt/steps-validation/t126-20261027/tools/ops/manage_management.py deploy qa-cerro /opt/steps-validation/t126-20261027/species-tariff-B.tar t126q --kind species-tariff
```

`t126b` solo tiene addons extraídos; verificar que no exista la base privada ni
baseline antes de reutilizarlo. Elegir run_id nuevo si el estado cambió. No
publicar sin aprobar la copia, conservar el mismo paquete y verificar flujo,
origen, menú y formulario en vivo. QA-Cerro debe conservar sus ejercicios y
aislamiento. Luego cerrar por el flujo interno silencioso y publicar/integrar
lo probado con `verify_handoff.py --require-pushed` aprobado.

Auditoría y adjunto privados: carpeta
`C:/Users/tito4/.codex/local-artifacts/helpdesk-heartbeat-20261027-1100/`.
Último comentario revisado de T126: 9749 (T124: 9737; T125: 9742). Volver a leer
comentarios antes del cierre. Los tres tickets continúan abiertos.

## Paquete C y prueba en cola

El fixture B trataba el grupo de especie como relación, pero el campo nativo
es una selección. Se corrigió para conservar su valor real, sin cambiar código
funcional de producto ni datos del destino. El paquete vigente es:

- Commit `815b056f1e79f3aa86efeac2c87e5fa2549e7d91`.
- SHA256 `7e38b3a590b99dd1cdc88f216555fb7ebb5f9c76fde2aede7c93b69d9e826ead`.
- `/opt/steps-validation/t126-20261027/species-tariff-C.tar`.

Se dejó **ejecutándose/en cola**:

```text
sudo python3 /opt/steps-validation/t126-20261027/tools/ops/manage_management.py qa development /opt/steps-validation/t126-20261027/species-tariff-C.tar t126d --kind species-tariff --wait-for-lease
```

El operador incorpora `--wait-for-lease` para estos ensayos privados: adquiere el
bloqueo compartido antes de leer la configuración y la línea base. Espera al
dueño actual sin detenerlo ni retirar la exclusión. No habilita publicación
automática. Sesión exec del chat: 32618. **Antes de lanzar otra prueba, comprobar
ese proceso y `/opt/steps-validation/management_development_t126d/`.** No duplicar
el ensayo ni asumir que ya terminó. Revisar logs y `qa_passed.json`.

Una vez aprobado C, publicar el paquete C en Desarrollo con run_id `t126d`;
continuar con copias nuevas de Cerro y QA-Cerro y ese mismo archivo. Los comandos
anteriores con paquete B quedaron superados. El código de producción no cambió.
