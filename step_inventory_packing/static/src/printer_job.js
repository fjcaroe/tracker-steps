/** @odoo-module **/
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export async function sendPrinterJob(profile, payload, nav = navigator) {
    const bytes = new TextEncoder().encode(payload);
    if (!bytes.length || bytes.length > 32768) throw new Error("La etiqueta excede el tamaño permitido.");
    if (profile.protocol === "serial") {
        if (!nav.serial) throw new Error("El navegador no ofrece puerto serie. Use el perfil PDF con su controlador.");
        const port = await nav.serial.requestPort(profile.serial_service_uuid ? { allowedBluetoothServiceClassIds: [profile.serial_service_uuid] } : {});
        let writer;
        try {
            await port.open({ baudRate: profile.baud_rate });
            writer = port.writable.getWriter();
            await writer.write(bytes);
        } finally {
            writer?.releaseLock();
            if (port.writable) await port.close();
        }
    } else if (profile.protocol === "ble") {
        if (!nav.bluetooth) throw new Error("El navegador no ofrece Bluetooth BLE. Use el perfil PDF.");
        const device = await nav.bluetooth.requestDevice({ filters: [{ services: [profile.service_uuid] }] });
        try {
            const server = await device.gatt.connect();
            const service = await server.getPrimaryService(profile.service_uuid);
            const characteristic = await service.getCharacteristic(profile.characteristic_uuid);
            for (let offset = 0; offset < bytes.length; offset += profile.chunk_size) {
                const chunk = bytes.slice(offset, offset + profile.chunk_size);
                if (characteristic.properties.write) await characteristic.writeValueWithResponse(chunk);
                else if (characteristic.properties.writeWithoutResponse) await characteristic.writeValueWithoutResponse(chunk);
                else throw new Error("La característica seleccionada no admite escritura.");
            }
        } finally {
            if (device.gatt.connected) device.gatt.disconnect();
        }
    } else if (profile.protocol === "usb") {
        if (!nav.usb) throw new Error("El navegador no ofrece WebUSB. Use el perfil PDF con su controlador.");
        const filter = { vendorId: profile.usb_vendor_id };
        if (profile.usb_product_id) filter.productId = profile.usb_product_id;
        const device = await nav.usb.requestDevice({ filters: [filter] });
        let claimed = false;
        try {
            await device.open();
            if (device.configuration?.configurationValue !== profile.usb_configuration) await device.selectConfiguration(profile.usb_configuration);
            await device.claimInterface(profile.usb_interface);
            claimed = true;
            const result = await device.transferOut(profile.usb_endpoint, bytes);
            if (result.status !== "ok" || result.bytesWritten !== bytes.length) throw new Error("La impresora no aceptó toda la etiqueta.");
        } finally {
            try { if (claimed) await device.releaseInterface(profile.usb_interface); }
            finally { if (device.opened) await device.close(); }
        }
    } else throw new Error("Seleccione un perfil de conexión directa.");
}

export class PrinterJob extends Component {
    static template = "step_inventory_packing.PrinterJob";
    static props = ["*"];
    setup() {
        this.state = useState({ busy: false, message: "", sent: false });
        this.action = useService("action");
        this.profile = this.props.action.params.profile;
    }
    async print() {
        if (this.state.busy) return;
        this.state.busy = true;
        this.state.message = "";
        try {
            if (!window.isSecureContext) throw new Error("La conexión a dispositivos requiere HTTPS.");
            // Device selection begins directly in the click handler; no RPC precedes it.
            await sendPrinterJob(this.profile, this.props.action.params.payload);
            this.state.sent = true;
            this.state.message = "Etiqueta enviada al dispositivo. Verifique la impresión física antes de reimprimir.";
        } catch (error) { this.state.message = error.message || String(error); }
        finally { this.state.busy = false; }
    }
    prepareReprint() { this.state.sent = false; }
}
registry.category("actions").add("step_printer_job", PrinterJob);
