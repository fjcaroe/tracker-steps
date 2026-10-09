// @vitest-environment jsdom
// Cada escenario de demostración muestra la situación que promete (base para capturas y para el trabajo visual).
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import App from '../app/App';
import { createDemoRuntime } from '../app/bootstrap';
import { SCENARIOS, type ScenarioName } from './demo';

afterEach(() => { cleanup(); vi.restoreAllMocks(); });
const open = async (name: ScenarioName) => {
  window.history.replaceState({}, '', `/?scenario=${name}`);
  const { runtime } = await createDemoRuntime();
  render(<App runtime={runtime} />);
  return runtime;
};

describe('escenarios de demostración', () => {
  it('lista los escenarios con descripción', () => { expect(Object.keys(SCENARIOS)).toHaveLength(7); });

  it('nuevo: bienvenida para crear cuenta', async () => {
    await open('nuevo');
    expect(await screen.findByRole('button', { name: 'Crear cuenta' })).toBeTruthy();
  });
  it('conductor: ve su servicio y puede iniciarlo', async () => {
    await open('conductor');
    fireEvent.click(await screen.findByRole('button', { name: 'Mis servicios' }));
    expect(await screen.findByText('Ruta prueba')).toBeTruthy();
  });
  it('beneficiaria: historial de colaciones', async () => {
    await open('beneficiaria');
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Colaciones' }));
    expect(await screen.findByText('Tus últimos registros')).toBeTruthy();
    expect(screen.getAllByText(/COL\/10\d/).length).toBeGreaterThanOrEqual(5);
  });
  it('pendientes: teléfono sin señal con operaciones por enviar y una rechazada con su motivo', async () => {
    await open('pendientes');
    expect(await screen.findByText(/por enviar|con problema/)).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: /Sincronización/ }));
    expect(await screen.findByText('El trabajador no está habilitado para recibir colación.')).toBeTruthy();
    expect(screen.getByText('Rechazada')).toBeTruthy();
  });
  it('multiempresa: pide elegir empresa y luego muestra módulos distintos', async () => {
    await open('multiempresa');
    fireEvent.click(await screen.findByRole('button', { name: 'Empresa A' }));
    expect(await screen.findByRole('button', { name: 'Abrir Tracker' })).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Abrir Colaciones' })).toBeTruthy();
  });
  it('Tracker demo does not contact production or reuse/mutate an existing token', async () => {
    const old = localStorage.getItem('steps_movil_token');
    localStorage.setItem('steps_movil_token', 'existing-test-token');
    const network = vi.spyOn(globalThis, 'fetch');
    try {
      await open('multiempresa');
      fireEvent.click(await screen.findByRole('button', { name: 'Empresa A' }));
      fireEvent.click(await screen.findByRole('button', { name: 'Abrir Tracker' }));
      fireEvent.click(await screen.findByRole('button', { name: 'Iniciar jornada ficticia' }));
      expect(await screen.findByText('Jornada ficticia en curso')).toBeTruthy();
      fireEvent.click(screen.getByRole('button', { name: 'Finalizar jornada ficticia' }));
      expect(screen.getByText('Jornada ficticia finalizada')).toBeTruthy();
      expect(network).not.toHaveBeenCalled();
      expect(localStorage.getItem('steps_movil_token')).toBe('existing-test-token');
    } finally { if (old === null) localStorage.removeItem('steps_movil_token'); else localStorage.setItem('steps_movil_token', old); }
  });
  it('supervisor: ve el servicio en curso con su pasajero', async () => {
    await open('supervisor');
    fireEvent.click(await screen.findByRole('button', { name: 'Abrir Movilización' }));
    expect(await screen.findByText('Pasajero Cuatro')).toBeTruthy();
  });
  it('sin módulos: explica el estado en vez de dejar la pantalla vacía', async () => {
    await open('sin-modulos');
    expect(await screen.findByText('Aún no tienes módulos habilitados')).toBeTruthy();
  });
});
