// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import { StartForm, FinishSheet } from './Journey';
import { catalogs, sessions } from '../lib/api';
import { outboxStore } from '../lib/sync';
import type { Active } from '../lib/queue';
vi.mock('../lib/api', async (original) => ({ ...await original<typeof import('../lib/api')>(),
  catalogs: { machines: vi.fn(), labors: vi.fn(), drivers: vi.fn(), implements: vi.fn(), fields: vi.fn(), costCenters: vi.fn(), fuelStatus: vi.fn() },
  sessions: { createWorkOrder: vi.fn(), start: vi.fn() },
}));
const machine={id:1,name:'Auto de copia',plate:'QA0046',cost_center_id:7,tank_capacity_liters:null,default_labor_id:8,fuel_consumption_unit:'kmpl' as const};
beforeEach(() => {
  localStorage.clear(); vi.mocked(catalogs.machines).mockResolvedValue([machine]);
  vi.mocked(catalogs.labors).mockResolvedValue([{id:8,activity_id:2,name:'Conducción'}]);
  vi.mocked(catalogs.costCenters).mockResolvedValue([{id:7,name:'Interno'}]);
  vi.mocked(catalogs.drivers).mockResolvedValue([{id:1,name:'Conductor',is_active:true}]);
  vi.mocked(catalogs.fields).mockResolvedValue([]);vi.mocked(catalogs.implements).mockResolvedValue([]);
  vi.mocked(sessions.createWorkOrder).mockResolvedValue({id:10});vi.mocked(sessions.start).mockResolvedValue({id:'qa',machine_id:1,started_at:new Date().toISOString(),ended_at:null,status:'open'});
});
afterEach(() => {cleanup();vi.resetAllMocks();});
it('preselects the single car and actual defaults; starts without invented meter or fuel', async () => {
  const started=vi.fn();render(<StartForm preset={null} onStarted={started}/>);
  await screen.findByText('Este vehículo trabaja por distancia.',{exact:false});
  expect(screen.queryByLabelText('Horómetro inicial')).toBeNull();
  expect((screen.getByLabelText('Litros en el estanque (opcional)') as HTMLInputElement).required).toBe(false);
  fireEvent.click(screen.getByRole('button',{name:'Iniciar jornada'}));
  await waitFor(()=>expect(started).toHaveBeenCalled());
  expect(sessions.createWorkOrder).toHaveBeenCalledWith(expect.objectContaining({machine_id:1,labor_id:8,cost_center_id:7,hourmeter_initial:null,fuel_tank_start_liters:null}));
  expect(sessions.start).toHaveBeenCalledWith(expect.objectContaining({driver_id:1}));
});
it('retains required meter and tank fields for machinery', async () => {
  vi.mocked(catalogs.machines).mockResolvedValue([{...machine,fuel_consumption_unit:'lph'}]);
  render(<StartForm preset={null} onStarted={vi.fn()}/>);
  const meter=await screen.findByLabelText('Horómetro inicial');
  expect((meter as HTMLInputElement).required).toBe(true);
  expect((screen.getByLabelText('Litros en el estanque') as HTMLInputElement).required).toBe(true);
});
it('closes a distance vehicle without fabricating missing readings or consumption', async () => {
  const active:Active={sessionId:'qa',machineId:1,machineName:'Auto',workOrderId:10,startedAt:Date.now(),hourmeterStart:null,tankStart:null,tankCapacity:null,distanceM:0,distanceBased:true};
  const done=vi.fn();render(<FinishSheet active={active} flush={async()=>{}} onCancel={vi.fn()} onDone={done}/>);
  expect(screen.queryByLabelText('Horómetro final')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Confirmar y cerrar'}));
  await waitFor(()=>expect(done).toHaveBeenCalled());
  expect(done.mock.calls[0][0].summary.fuelUsedL).toBeNull();
  expect(outboxStore.ops().find((o)=>o.kind==='wo_finish')).toMatchObject({body:{hourmeter_final:null,fuel_tank_end_liters:null}});
});
