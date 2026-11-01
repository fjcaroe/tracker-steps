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
