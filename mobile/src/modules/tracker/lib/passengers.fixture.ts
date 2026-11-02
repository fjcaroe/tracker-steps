import type { Manifest } from './passengers';
export const manifestFixture: Manifest = {
  id: 'service', name: 'Servicio de prueba', route_id: 'route', route_name: 'Ruta Norte', route_status: 'assigned',
  machine_id: 1, machine_name: 'Bus de prueba', plate: 'QA0046', driver_user_id: 2, driver_name: 'Conductor de prueba', capacity: 3,
  stops: [{ id: 'a', name: 'Origen', scheduled_at: '2026-11-02T11:00:00Z', lat: null, lon: null }, { id: 'b', name: 'Destino', scheduled_at: '2026-11-02T12:00:00Z', lat: null, lon: null }],
  passengers: [1, 2, 3].map((id) => ({ id: String(id), name: `Pasajero ${id}`, document: `TEST-${id}`, boarding_stop_id: 'a', alighting_stop_id: 'b', seat: id === 3 ? null : id, state: 'pending' })),
  manifest_version: 0, occupied: 0, events: [],
};
