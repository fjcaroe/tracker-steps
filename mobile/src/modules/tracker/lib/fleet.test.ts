import {afterEach,expect,it,vi} from 'vitest';
import {loadHardwareFleet,FleetAccessError,recentPosition} from './fleet';
afterEach(()=>vi.unstubAllGlobals());
it('reads only the same-origin Odoo fleet without attaching the classic token',async()=>{
 const fetch=vi.fn().mockResolvedValue({status:200,ok:true,type:'basic',headers:new Headers({'content-type':'application/json'}),json:async()=>({items:[]})});vi.stubGlobal('fetch',fetch);
 await loadHardwareFleet();expect(fetch).toHaveBeenCalledWith('/steps_tracker/api/fleet/snapshot?limit=500',expect.objectContaining({credentials:'same-origin',cache:'no-store',redirect:'manual',headers:{Accept:'application/json'}}));
});
it('rejects a login page or denied role instead of treating it as an empty fleet',async()=>{
 for(const status of [401,403,404,0]){vi.stubGlobal('fetch',vi.fn().mockResolvedValue({status,type:'basic',headers:new Headers()}));await expect(loadHardwareFleet()).rejects.toBeInstanceOf(FleetAccessError);}
});
it('does not call a newly received old fix a current position',()=>{
 const stamp=new Date().toISOString();const p={signal_state:'received',position_stale:false,last_position:{quality:'gps',recorded_at:'2020-01-01T00:00:00Z',received_at:stamp}};
 expect(recentPosition(p as Parameters<typeof recentPosition>[0])).toBe(false);
});
const reply=(data:unknown)=>({status:200,ok:true,type:'basic',headers:new Headers({'content-type':'application/json'}),json:async()=>data});
it('projects an unassigned capture device with only a masked identifier for its manager',async()=>{
 const scope={tenant_id:'one',user_id:'2',role:'manager',items:[]};
 const fetch=vi.fn().mockResolvedValueOnce(reply(scope)).mockResolvedValueOnce(reply({items:[{id:'r1',imei:'000000000000001',phone:'private-test',notes:'not for the map',asset_id:null,asset_name:null,commissioning:{mode:'capture',lat:-33,lon:-70,fix_at:'2026-11-01T00:00:00Z'}}]})).mockResolvedValueOnce(reply(scope));
 vi.stubGlobal('fetch',fetch);const data=await loadHardwareFleet();
 expect(data.installations?.[0].label).toBe('GPS · ••••0001');expect(data.installations?.[0].lat).toBe(-33);
 expect(JSON.stringify(data)).not.toContain('private-test');expect(JSON.stringify(data)).not.toContain('000000000000001');
});
it('never requests private GPS configuration for viewers',async()=>{
 const fetch=vi.fn().mockResolvedValue(reply({role:'viewer',items:[]}));vi.stubGlobal('fetch',fetch);await loadHardwareFleet();expect(fetch).toHaveBeenCalledTimes(1);
});
it('discards private diagnostics if company or identity changes during the read',async()=>{
 const before={tenant_id:'one',user_id:'2',role:'manager',items:[]};const after={...before,tenant_id:'two'};
 const fetch=vi.fn().mockResolvedValueOnce(reply(before)).mockResolvedValueOnce(reply({items:[]})).mockResolvedValueOnce(reply(after)).mockResolvedValueOnce(reply(after));vi.stubGlobal('fetch',fetch);
 const result=await loadHardwareFleet();expect(result.tenant_id).toBe('two');expect(result.installations).toEqual([]);
});
