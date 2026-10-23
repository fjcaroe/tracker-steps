/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { DateTime } from "luxon";

const WEIGHT_FIELDS = [
    ["step_fruit_gross_kg", "Peso bruto"],
    ["step_fruit_truck_tare_kg", "Destare camión"],
    ["step_fruit_container_tare_kg", "Destare envases"],
    ["step_fruit_transfer_tare_kg", "Destare unidades de traslado"],
];
const UNIT_FIELDS = [["gross_kg", "Peso bruto"], ["tare_kg", "Destare"]];

export function parseScaleWeight(raw, pattern, factor) {
    const match = new RegExp(pattern).exec(raw);
    if (!match || !match[1]) {
        return null;
    }
    const value = Number(match[1].replace(",", ".")) * Number(factor);
    return Number.isFinite(value) && value >= 0 ? value : null;
}

export class ScaleCapture extends Component {
    static template = "step_inventory_packing.ScaleCapture";
    static props = { ...standardFieldProps };

    setup() {
        this.notification = useService("notification");
        this.weightFields = "gross_kg" in this.props.record.data ? UNIT_FIELDS : WEIGHT_FIELDS;
        this.state = useState({ target: this.weightFields[0][0], busy: false });
    }

    get profile() {
        const data = this.props.record.data;
        return {
            protocol: data.step_scale_protocol,
            service: data.step_scale_service_uuid,
            characteristic: data.step_scale_characteristic_uuid,
            serialService: data.step_scale_serial_service_uuid,
            baudRate: data.step_scale_baud_rate,
            pattern: data.step_scale_weight_pattern,
            factor: data.step_scale_kg_factor,
        };
    }

    async capture() {
        if (this.state.busy) {
            return;
        }
        const profile = this.profile;
        if (!profile.protocol || !profile.pattern) {
            this.notification.add(_t("Seleccione un perfil de balanza configurado."), { type: "warning" });
            return;
        }
        this.state.busy = true;
        try {
            // La solicitud de dispositivo debe comenzar en el gesto del usuario.
            const raw = profile.protocol === "ble"
                ? await this.readBle(profile)
                : await this.readSerial(profile);
            const kg = parseScaleWeight(raw, profile.pattern, profile.factor);
            if (kg === null) {
                throw new Error(_t("La trama no contiene un peso válido según el perfil."));
            }
            await this.props.record.update({
                [this.state.target]: kg,
                step_scale_read_raw: raw.slice(0, 250),
                step_scale_read_at: DateTime.utc(),
            });
            this.notification.add(_t("Lectura registrada: %s kg", kg), { type: "success" });
        } catch (error) {
            this.notification.add(error.message || String(error), { type: "danger" });
        } finally {
            this.state.busy = false;
        }
    }

    async readBle(profile) {
        if (!window.isSecureContext || !navigator.bluetooth) {
            throw new Error(_t("Este navegador no ofrece Bluetooth BLE; use HTTPS y un navegador compatible."));
        }
        const device = await navigator.bluetooth.requestDevice({
            acceptAllDevices: true, optionalServices: [profile.service],
        });
        try {
            const server = await device.gatt.connect();
            const service = await server.getPrimaryService(profile.service);
            const characteristic = await service.getCharacteristic(profile.characteristic);
            if (characteristic.properties.read) {
                return this.decode(await characteristic.readValue());
            }
            if (!characteristic.properties.notify) {
                throw new Error(_t("La característica BLE no permite leer ni recibir notificaciones."));
            }
            await characteristic.startNotifications();
            return await new Promise((resolve, reject) => {
                const timer = setTimeout(() => {
                    characteristic.removeEventListener("characteristicvaluechanged", onValue);
                    reject(new Error(_t("La balanza no envió una lectura en 15 segundos.")));
                }, 15000);
                const onValue = (event) => {
                    const raw = this.decode(event.target.value);
                    if (parseScaleWeight(raw, profile.pattern, profile.factor) !== null) {
                        clearTimeout(timer);
                        characteristic.removeEventListener("characteristicvaluechanged", onValue);
                        resolve(raw);
                    }
                };
                characteristic.addEventListener("characteristicvaluechanged", onValue);
            });
        } finally {
            if (device.gatt.connected) {
                device.gatt.disconnect();
            }
        }
    }

    decode(value) {
        return new TextDecoder().decode(new Uint8Array(value.buffer, value.byteOffset, value.byteLength));
    }

    async readSerial(profile) {
        if (!window.isSecureContext || !navigator.serial) {
            throw new Error(_t("Este navegador no ofrece puertos serie; use HTTPS y Chrome de escritorio."));
        }
        const options = profile.serialService
            ? { allowedBluetoothServiceClassIds: [profile.serialService] } : {};
        const port = await navigator.serial.requestPort(options);
        let reader;
        let timer;
        try {
            await port.open({ baudRate: profile.baudRate });
            reader = port.readable.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            timer = setTimeout(() => reader.cancel(), 15000);
            while (true) {
                const { value, done } = await reader.read();
                if (done) {
                    throw new Error(_t("La balanza no envió una lectura válida en 15 segundos."));
                }
                buffer = (buffer + decoder.decode(value, { stream: true })).slice(-1024);
                if (parseScaleWeight(buffer, profile.pattern, profile.factor) !== null) {
                    return buffer;
                }
            }
        } finally {
            clearTimeout(timer);
            if (reader) {
                reader.releaseLock();
            }
            if (port.readable) {
                await port.close();
            }
        }
    }
}

registry.category("fields").add("step_scale_capture", {
    component: ScaleCapture,
    supportedTypes: ["char"],
});
