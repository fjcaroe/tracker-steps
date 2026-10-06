// Exercise the production transport code with simulated devices; no hardware access.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
function exported(file, names) {
    const source = fs.readFileSync(path.join(root, file), 'utf8').replace(/^import .*;\r?$/gm, '').replace(/export /g, '');
    return Function('Component', 'registry', 'standardFieldProps', 'luxon', source + '\nreturn {' + names + '};')(
        class {}, { category: () => ({ add() {} }) }, {}, {DateTime: {utc: () => 'QA_TIMESTAMP'}});
}
const { sendPrinterJob } = exported('step_inventory_packing/static/src/printer_job.js', 'sendPrinterJob');
const { parseScaleWeight, ScaleCapture } = exported('step_inventory_packing/static/src/scale_capture.js', 'parseScaleWeight, ScaleCapture');
const pattern = 'ST,([-+]?\\d+(?:[.,]\\d+)?)kg\\r?\\n';
assert.equal(parseScaleWeight('ST,12,5kg\r\n', pattern, 1), 12.5);
assert.equal(parseScaleWeight('US,12.5kg\n', pattern, 1), null);
assert.equal(parseScaleWeight('ST,-2kg\n', pattern, 1), null);
assert.equal(parseScaleWeight('ST,1250kg\n', pattern, 0.001), 1.25);
let listener, scaleDisconnected = false, notificationsStopped = false;
const scaleCharacteristic = { properties: { notify: true }, addEventListener: (_name, callback) => { listener = callback; },
    removeEventListener: () => { listener = null; }, stopNotifications: async () => { notificationsStopped = true; },
    startNotifications: async () => { for (const fragment of ['ST,12', ',5kg\r\n']) listener({ target: { value: fragment } }); } };
const scaleDevice = { gatt: { connected: true, connect: async () => ({ getPrimaryService: async () => ({ getCharacteristic: async () => scaleCharacteristic }) }),
    disconnect: () => { scaleDisconnected = true; } } };
globalThis.window = { isSecureContext: true };
Object.defineProperty(globalThis, 'navigator', { value: { bluetooth: { requestDevice: async () => scaleDevice } }, configurable: true });
const raw = await ScaleCapture.prototype.readBle.call({ decode: value => value }, { service: 'service', characteristic: 'characteristic', pattern, factor: 1 });
assert.equal(parseScaleWeight(raw, pattern, 1), 12.5);
assert.ok(scaleDisconnected && notificationsStopped && !listener);

const profile = { protocol: 'serial', baud_rate: 9600 };
let closed = 0, released = 0, printed = '';
const port = { writable: { getWriter: () => ({ write: async bytes => { printed = new TextDecoder().decode(bytes); }, releaseLock: () => released++ }) },
    open: async options => assert.equal(options.baudRate, 9600), close: async () => closed++ };
await sendPrinterJob(profile, '^XA^XZ', { serial: { requestPort: async () => port } });
assert.equal(printed, '^XA^XZ');
assert.equal(closed, 1); assert.equal(released, 1);
port.writable.getWriter = () => ({ write: async () => { throw new Error('Simulated disconnect'); }, releaseLock: () => released++ });
await assert.rejects(sendPrinterJob(profile, '^XA^XZ', { serial: { requestPort: async () => port } }), /disconnect/);
assert.equal(closed, 2); assert.equal(released, 2);

let usbReleased = false, usbClosed = false;
const usb = { opened: true, configuration: { configurationValue: 1 }, open: async () => {}, claimInterface: async () => {},
    transferOut: async (_endpoint, bytes) => ({ status: 'ok', bytesWritten: bytes.length }),
    releaseInterface: async () => { usbReleased = true; }, close: async () => { usbClosed = true; } };
await sendPrinterJob({ protocol: 'usb', usb_vendor_id: 123, usb_configuration: 1, usb_interface: 0, usb_endpoint: 1 }, '^XA^XZ', { usb: { requestDevice: async () => usb } });
assert.ok(usbReleased && usbClosed);
usb.transferOut = async () => ({ status: 'stall', bytesWritten: 0 });
await assert.rejects(sendPrinterJob({ protocol: 'usb', usb_vendor_id: 123, usb_configuration: 1, usb_interface: 0, usb_endpoint: 1 }, '^XA^XZ', { usb: { requestDevice: async () => usb } }), /etiqueta/);

const chunks = [];
let disconnected = false;
const characteristic = { properties: { writeWithoutResponse: true }, writeValueWithoutResponse: async bytes => chunks.push(bytes.length) };
const device = { gatt: { connected: true, connect: async () => ({ getPrimaryService: async () => ({ getCharacteristic: async () => characteristic }) }),
    disconnect: () => { disconnected = true; } } };
await sendPrinterJob({ protocol: 'ble', service_uuid: 'service', characteristic_uuid: 'characteristic', chunk_size: 4 }, '^XA12345^XZ', { bluetooth: { requestDevice: async () => device } });
assert.deepEqual(chunks, [4, 4, 3]); assert.ok(disconnected);
await assert.rejects(sendPrinterJob(profile, '^XA^XZ', {}), /navegador/);
await assert.rejects(sendPrinterJob(profile, 'x'.repeat(32769), {}), /tamaño/);
console.log('DEVICE_SIMULATION_OK: scale frames, serial/BLE/USB writes, disconnect cleanup and payload bounds');
