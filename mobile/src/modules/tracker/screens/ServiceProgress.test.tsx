// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { api } from '../lib/api';
import { manifestFixture } from '../lib/passengers.fixture';
import ServiceProgress, { ServiceProgressMonitor } from './ServiceProgress';

vi.mock('../lib/api', async (original) => ({ ...await original<typeof import('../lib/api')>(), api: vi.fn() }));
const stop = { ...manifestFixture.stops[0], arrived_at: null, departed_at: null, eta: null,
  delay_minutes: 0, arrival_notes: null, departure_notes: null };
const item = { id: manifestFixture.id, name: manifestFixture.name, route_name: 'Ruta de prueba',
  route_status: 'assigned', driver_name: 'Conductor de prueba', version: 0, closure: null, stops: [stop] };
beforeEach(() => {
  vi.resetAllMocks();
  vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible');
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('shows scheduled stops without a connection and enables explicit recording once connected', async () => {
  const closed = vi.fn();
  vi.mocked(api).mockResolvedValueOnce(item).mockResolvedValueOnce({ ...item, version: 1, stops: [
    { ...stop, arrived_at: '2026-11-15T13:00:00Z', delay_minutes: 11 },
  ] });
  const { rerender } = render(<ServiceProgress manifest={manifestFixture} pending={0} online={false} onClosed={closed} />);
  expect(screen.getByText(stop.name)).toBeTruthy();
  expect(api).not.toHaveBeenCalled();
  rerender(<ServiceProgress manifest={manifestFixture} pending={0} online onClosed={closed} />);
  fireEvent.change(await screen.findByLabelText('Desvío o novedad de la parada'), { target: { value: 'Desvío por trabajos' } });
  fireEvent.click(screen.getByRole('button', { name: 'Registrar llegada de ' + stop.name }));
  expect(await screen.findByText('Retraso de 11 min')).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Registrar salida de ' + stop.name })).toBeTruthy();
  expect(api).toHaveBeenLastCalledWith('/mobile/services/' + item.id + '/progress',
    expect.objectContaining({ method: 'POST', body: expect.stringContaining('Desvío por trabajos') }));
  expect(closed).not.toHaveBeenCalled();
});

it('refreshes the supervisor stop view without offering driver controls', async () => {
  vi.mocked(api).mockResolvedValueOnce([{ ...item, stops: [{ ...stop, arrival_notes: 'Aviso de desvío' }] }]);
  render(<ServiceProgressMonitor />);
  expect(await screen.findByText('Aviso de desvío')).toBeTruthy();
  await waitFor(() => expect(api).toHaveBeenCalledWith('/mobile/services/progress', expect.anything()));
  expect(screen.queryByRole('button')).toBeNull();
});
