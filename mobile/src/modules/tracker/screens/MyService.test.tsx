// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import MyService from './MyService';
import { api, type PassengerService } from '../lib/api';
vi.mock('../lib/api', () => ({ api: vi.fn() }));
afterEach(() => { cleanup(); vi.resetAllMocks(); });

const service: PassengerService = {
  id: 'service', name: 'Servicio de prueba', route_id: 'route', route_name: 'Ruta Norte',
  machine_id: 1, machine_name: 'Bus de prueba', plate: 'QA0046', driver_user_id: 2, driver_name: 'Conductor de prueba', capacity: 3,
  stops: [{ id: 'a', name: 'Origen', scheduled_at: '2026-11-02T11:00:00Z', lat: null, lon: null }, { id: 'b', name: 'Destino', scheduled_at: '2026-11-02T12:00:00Z', lat: null, lon: null }],
  passengers: [1, 2, 3].map((id) => ({ id: String(id), name: `Pasajero ${id}`, document: `TEST-${id}`, boarding_stop_id: 'a', alighting_stop_id: 'b', seat: id === 3 ? null : id })),
};

it('renders assigned service, three passengers, stops and seats read-only', async () => {
  vi.mocked(api).mockResolvedValue([service]);
  render(<MyService />);
  expect(await screen.findByText('Servicio de prueba')).toBeTruthy();
  for (const id of [1, 2, 3]) expect(screen.getByText(`Pasajero ${id}`)).toBeTruthy();
  expect(screen.getByText('Sin asiento asignado')).toBeTruthy();
  expect(screen.getByText('Asiento 1')).toBeTruthy();
  expect(screen.queryByRole('button')).toBeNull();
  expect(api).toHaveBeenCalledWith('/mobile/services?mine=true', { cache: 'no-store' });
});

it('shows an empty state with no assigned services', async () => {
  vi.mocked(api).mockResolvedValue([]);
  render(<MyService />);
  expect(await screen.findByText('No tienes servicios de pasajeros asignados.')).toBeTruthy();
});

it('shows an explicit failure and retries without a cached passenger manifest', async () => {
  vi.mocked(api).mockRejectedValueOnce(new Error('Sin conexión')).mockResolvedValueOnce([service]);
  render(<MyService />);
  expect(await screen.findByRole('alert')).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: 'Reintentar servicio' }));
  expect(await screen.findByText('Servicio de prueba')).toBeTruthy();
});

it('warns when the assigned route has been cancelled', async () => {
  vi.mocked(api).mockResolvedValue([{ ...service, route_status: 'cancelled' }]);
  render(<MyService />);
  expect(await screen.findByText('Ruta cancelada. Confirma el servicio con tu supervisor.')).toBeTruthy();
});
