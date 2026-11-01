// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import HardwareFleet from './HardwareFleet';
import {FleetAccessError,loadHardwareFleet,type HardwareFleet as Fleet} from '../lib/fleet';
vi.mock('../lib/fleet',async()=>({...await vi.importActual('../lib/fleet'),loadHardwareFleet:vi.fn()}));
vi.mock('../components/MapView',()=>({default:({markers}: {markers:{kind:string;label:string}[]})=><div data-testid="map">{markers.map((m,i)=><span key={i} data-kind={m.kind}>{m.label}</span>)}</div>}));
afterEach(()=>{cleanup();vi.resetAllMocks();});
const current=()=>new Date().toISOString();
function fixture():Fleet {return {tenant:'Cerro QA',tenant_id:'t1',user_id:'2',total:3,next_cursor:null,generated_at:current(),items:[
 {asset_id:'a1',name:'Auto GPS',plate:'QA0001',device:{brand:'Coban',model:'401C'},signal_state:'received',motion_state:'moving',position_stale:false,last_position:{id:'p1',lat:-35.4,lon:-71.6,recorded_at:current(),received_at:current(),speed_kmh:15,quality:'gps'}},
 {asset_id:'a2',name:'Auto antiguo',plate:null,device:null,signal_state:'stale',motion_state:'unknown',position_stale:true,last_position:{id:'p2',lat:-35,lon:-71,recorded_at:'2020-01-01T00:00:00Z',received_at:'2020-01-01T00:00:00Z',speed_kmh:70,quality:'gps'}},
 {asset_id:'a3',name:'Sin posición',plate:null,device:null,signal_state:'no_signal',motion_state:'unknown',position_stale:true,last_position:null},
 ]};}
it('shows hardware positions with no journey and identifies stale/missing positions',async()=>{
 vi.mocked(loadHardwareFleet).mockResolvedValue(fixture());render(<HardwareFleet onBack={()=>{}}/>);
 expect(await screen.findByText('Cerro QA')).toBeTruthy();
 expect(screen.getByText('En movimiento')).toBeTruthy();expect(screen.getByText('Esperando primera posición GPS')).toBeTruthy();
 expect(screen.getByText(/Auto antiguo · Sin patente/).getAttribute('data-kind')).toBe('stale');
 expect(screen.getByRole('button',{name:'Ver Auto GPS en el mapa'})).toBeTruthy();
 expect(screen.queryByText(/70.0 km/)).toBeNull();
});
it('clears locations when access is revoked and offers Odoo login',async()=>{
 vi.mocked(loadHardwareFleet).mockResolvedValueOnce(fixture()).mockRejectedValueOnce(new FleetAccessError('Acceso retirado'));
 render(<HardwareFleet onBack={()=>{}}/>);await screen.findByText('Cerro QA');fireEvent.click(screen.getByRole('button',{name:'Actualizar'}));
 expect(await screen.findByRole('alert')).toBeTruthy();expect(screen.queryByTestId('map')).toBeNull();expect(screen.getByRole('link',{name:'Entrar con Odoo'})).toBeTruthy();
});
it('retains clearly marked last known positions during a network outage',async()=>{
 vi.mocked(loadHardwareFleet).mockResolvedValueOnce(fixture()).mockRejectedValueOnce(new Error('Sin conexión'));
 render(<HardwareFleet onBack={()=>{}}/>);await screen.findByText('Cerro QA');fireEvent.click(screen.getByRole('button',{name:'Actualizar'}));
 await screen.findByRole('alert');expect(screen.queryByText('En movimiento')).toBeNull();
 await waitFor(()=>expect(screen.getByText(/Auto GPS · QA0001/).getAttribute('data-kind')).toBe('stale'));
});
it('shows an empty company without inventing vehicles or positions',async()=>{
 vi.mocked(loadHardwareFleet).mockResolvedValue({...fixture(),items:[],total:0});render(<HardwareFleet onBack={()=>{}}/>);
 expect(await screen.findByText(/Todavía no hay vehículos registrados/)).toBeTruthy();
});
it('shows a real bench position without creating or requiring a vehicle',async()=>{
 vi.mocked(loadHardwareFleet).mockResolvedValue({...fixture(),items:[],total:0,role:'manager',installations:[{id:'r1',label:'GPS · ••••0001',asset_id:null,asset_name:null,mode:'capture',last_seen_at:current(),fix_at:current(),fix_received_at:current(),lat:-33,lon:-70}]});
 render(<HardwareFleet onBack={()=>{}}/>);await screen.findByText('GPS · ••••0001');
 expect(screen.getByText('Posición GPS recibida en prueba')).toBeTruthy();expect(screen.getByText('Sin vehículo asociado')).toBeTruthy();
 expect(screen.queryByText(/Todavía no hay vehículos registrados/)).toBeNull();expect(screen.getByRole('link',{name:'Asociar vehículo y validar seguimiento'})).toBeTruthy();
 expect(screen.getByText(/GPS en prueba ·/).getAttribute('data-kind')).toBe('test');
});
it('does not map a previous fix when reception is disabled',async()=>{
 vi.mocked(loadHardwareFleet).mockResolvedValue({...fixture(),items:[],total:0,installations:[{id:'r1',label:'GPS · ••••0001',asset_id:null,asset_name:null,mode:'disabled',last_seen_at:current(),fix_at:current(),fix_received_at:current(),lat:-33,lon:-70}]});
 render(<HardwareFleet onBack={()=>{}}/>);await screen.findByText('Recepción deshabilitada');expect(screen.getByTestId('map').children.length).toBe(0);
});
