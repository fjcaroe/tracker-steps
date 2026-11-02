// @vitest-environment jsdom
import { IDBFactory } from 'fake-indexeddb';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import MyService from './MyService';
import { api } from '../lib/api';
import { manifestFixture as fixture } from '../lib/passengers.fixture';
import { passengerStore, project } from '../lib/passengers';
vi.mock('../lib/api', async (original) => ({ ...await original<typeof import('../lib/api')>(), api: vi.fn() }));
beforeEach(() => {
  vi.stubGlobal('indexedDB', new IDBFactory());
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true);
  vi.mocked(api).mockImplementation(async (path) => (path === '/mobile/services?mine=true' ? [fixture] : structuredClone(fixture)) as never);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('requires explicit preparation and finds people by name and state without enabling unattended QR actions', async () => {
  render(<MyService userId={2} />);
  expect(await screen.findByText('Servicio de prueba')).toBeTruthy();
  expect((screen.getAllByRole('button', { name: 'Registrar subida' })[0] as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('Buscar pasajero'), { target: { value: 'Pasajero 2' } });
  expect(screen.queryByText('Pasajero 1')).toBeNull();
  expect(screen.getByText('Pasajero 2')).toBeTruthy();
  fireEvent.change(screen.getByLabelText('Código del pasajero'), { target: { value: 'steps:passenger:1' } });
  fireEvent.click(screen.getByRole('button', { name: 'Buscar código' }));
  expect(screen.getByText('Pasajero 1')).toBeTruthy();
  expect(api).not.toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ method: 'POST' }));
});

it('performs the entire service offline, preserves the queue, and shows occupancy and pending status', async () => {
  await passengerStore.prepare(2, fixture);
  vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
  render(<MyService userId={2} />);
  await screen.findByText('Servicio de prueba');
  const card = (name: string) => within(screen.getByText(name).closest('li')!);
  fireEvent.click(card('Pasajero 1').getByRole('button', { name: 'Registrar subida' }));
  await waitFor(() => expect(card('Pasajero 1').getByText('A bordo')).toBeTruthy());
  fireEvent.click(card('Pasajero 2').getByRole('button', { name: 'Registrar subida' }));
  await waitFor(() => expect(card('Pasajero 2').getByText('A bordo')).toBeTruthy());
  vi.spyOn(window, 'confirm').mockReturnValue(true);
  fireEvent.click(card('Pasajero 3').getByRole('button', { name: 'Marcar ausente' }));
  await waitFor(() => expect(card('Pasajero 3').getByText('Ausente')).toBeTruthy());
  for (const name of ['Pasajero 1', 'Pasajero 2']) {
    fireEvent.click(card(name).getByRole('button', { name: 'Registrar bajada' }));
    await waitFor(() => expect(card(name).getByText('Descendió')).toBeTruthy());
  }
  const [saved] = await passengerStore.read(2);
  expect(saved.queue).toHaveLength(5); expect(project(saved)?.occupied).toBe(0);
  expect(saved.queue.every((e) => e.lat === null && e.lon === null)).toBe(true);
  expect(api).not.toHaveBeenCalled();
});

it('shows no assignment and a cancelled service without allowing boarding', async () => {
  vi.mocked(api).mockResolvedValueOnce([]);
  const view = render(<MyService userId={2} />);
  await screen.findByText('No tienes servicios de pasajeros asignados.');
  view.unmount();
  vi.mocked(api).mockImplementation(async (path) => (path === '/mobile/services?mine=true' ? [{ ...fixture, route_status: 'cancelled' }] : { ...fixture, route_status: 'cancelled' }) as never);
  render(<MyService userId={2} />);
  await screen.findByText('Ruta cancelada. Confirma el servicio con tu supervisor.');
  expect((screen.getAllByRole('button', { name: 'Registrar subida' })[0] as HTMLButtonElement).disabled).toBe(true);
});
