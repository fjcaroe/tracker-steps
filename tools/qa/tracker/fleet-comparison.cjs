/* Comparison fixtures live only in browser responses. Real mode permits read requests only. */
const {chromium}=require('playwright');
let summarizeFixture;
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const output=process.env.GPS_UI_OUTPUT,dist=process.env.GPS_OPERATIONS_DIST;
const proof=process.env.GPS_BROWSER_PROOF?JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8').replace(/^\uFEFF/,'')):null;
const fixture=!proof,host=proof?.host||'desarrollo.stepsapp.cl';
const ids=[1,2,3].map(i=>'00000000-0000-4000-8000-'+String(i).padStart(12,'0'));
const now=Date.now(),start=new Date(now);start.setUTCHours(2,58,0,0);
if(start.getTime()>now)start.setUTCDate(start.getUTCDate()-1);
const points=(vehicle,count)=>Array.from({length:count},(_,i)=>({
 id:vehicle+'-'+i,recorded_at:new Date(start.getTime()+i*60000).toISOString(),
 received_at:new Date(start.getTime()+i*60000).toISOString(),lat:(vehicle===1?-33.4:-36.8)-i*.001*vehicle,
 lon:vehicle===1?-70.6:-73,speed_kmh:20*vehicle,quality:'gps',acc:null,external_power:null,
}));
const identity={user_id:100,user:'QA comparación',company_id:2,company:'Empresa QA',tenant_key:'QA:2',role:'manager',csrf_token:'fixture-only'};
let denied=false,partial=false,restricted=false;
const unexpected=[],errors=[];
(async()=>{
 summarizeFixture=(await import('../../../src/services/operationsMetrics.ts')).operationsMetrics;
 fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 if(proof)await context.addCookies([
  {name:'session_id',value:proof.session_id,domain:host,path:'/',secure:true,httpOnly:true},
  {name:'cids',value:String(proof.company_id),domain:host,path:'/',secure:true},
 ]);
 const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url());
  const json=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  if(dist&&url.hostname===host&&url.pathname.startsWith('/web_tracker/')){
   const root=path.resolve(dist),file=path.resolve(root,url.pathname.slice('/web_tracker/'.length)||'index.html');
   assert.ok(file.startsWith(root+path.sep));
   return route.fulfill({status:200,contentType:({'.js':'application/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});
  }
  if(fixture&&url.pathname==='/steps_tracker/context')return json(restricted?{...identity,company_id:3,tenant_key:'QA:3'}:identity);
  if(fixture&&url.pathname.startsWith('/steps_tracker/api/')){
   assert.equal(request.method(),'GET');
   const endpoint=url.pathname.replace('/steps_tracker/api/','');
   const assets=ids.slice(0,restricted?1:3).map((id,i)=>({
    asset_id:id,name:'Vehículo QA '+(i+1),plate:'QA-00'+(i+1),type:'car',cost_center:null,responsible:null,
    created_at:new Date(now-86400000).toISOString(),position_stale:false,signal_state:'received',motion_state:'moving',protection_state:'disarmed',
    last_position:points(1,4).at(-1),device:null,capabilities:{tracking:'approved',remote_start_inhibit:'not_approved'},
   }));
   if(endpoint==='fleet/snapshot')return json({items:assets,total:assets.length,next_cursor:null,tenant:identity.company});
   if(endpoint==='zones')return json([]);
   if(endpoint==='configuration')return json({items:[],reminders:[],today:'2026-11-05'});
   if(endpoint==='view-preferences/fleet')return json(null);
   if(endpoint==='assets/analytics'){
    const requested=url.searchParams.get('asset_ids').split(',');
    assert.ok(requested.length<=50);
    if(denied&&requested.includes(ids[1]))return json({detail:'Acceso revocado al vehículo QA-002'},403);
    const pending=partial;partial=false;
    return json({items:requested.map(id=>{
     const index=ids.indexOf(id);assert.ok(index>=0&&(!restricted||index===0));
     const m=summarizeFixture(index===2?[]:points(index+1,4),Date.parse(url.searchParams.get('since')),Date.parse(url.searchParams.get('until')));
     return {asset_id:id,complete:!(pending&&index===1),pending_hours:pending&&index===1?1:0,
      metrics:{point_count:m.points.length,distance_m:m.distanceM,moving_seconds:m.movingSeconds,stop_count:m.stops.length,gap_count:m.gapCount,max_speed:m.maxReportedSpeed,first_at:m.points[0]?.recorded_at,last_at:m.points.at(-1)?.recorded_at},
      daily:m.daily.map(d=>({day:d.day,point_count:2,distance_m:d.km*1000,moving_seconds:d.movingMinutes*60,stop_count:0,gap_count:0}))};
    })});
   }
   if(endpoint.endsWith('/positions')){
    const id=endpoint.split('/')[1],index=ids.indexOf(id);
    assert.ok(index>=0&&(!restricted||index===0));
    if(index===1&&denied)return json({detail:'Acceso revocado al vehículo QA-002'},403);
    if(index===2)return json({items:[],next_cursor:null});
    if(index===1&&partial){
     const pageNumber=Number(url.searchParams.get('before')||0);
     return json({items:[points(2,22)[pageNumber]],next_cursor:pageNumber<21?String(pageNumber+1):null});
    }
    return json({items:points(index+1,4).reverse(),next_cursor:null});
   }
   unexpected.push(endpoint);return route.abort();
  }
  if(fixture&&url.pathname.startsWith('/web/dataset/call_kw/')){
   const payload=request.postDataJSON(),p=payload.params;
   const rpc=data=>json({jsonrpc:'2.0',id:payload.id,result:data});
   if(p.model==='ir.ui.menu'&&p.method==='load_menus')return rpc({});
   if(p.model==='res.users'&&p.method==='read')return rpc([{id:100,company_ids:[2,3]}]);
   if(p.model==='res.company'&&p.method==='search_read')return rpc([{id:2,name:'Empresa QA'},{id:3,name:'Empresa restringida'}]);
   unexpected.push(p.model+':'+p.method);return route.abort();
  }
  if(url.hostname===host&&!['GET','HEAD'].includes(request.method())){
   if(!fixture&&url.pathname.startsWith('/web/dataset/call_kw/')){
    const method=request.postDataJSON().params.method;
    if(['search_read','read','check_access_rights','load_menus'].includes(method))return route.continue();
   }
   unexpected.push(request.method()+' '+url.pathname);return route.abort();
  }
  return route.continue();
 });
 const settle=async()=>{
  await page.locator('.fleet-comparison').waitFor();
  await page.getByText('Calculando estadísticas de los vehículos seleccionados…',{exact:true}).waitFor({state:'hidden'});
 };
 try{
  await page.goto('https://'+host+'/web_tracker/#ops');
  await page.getByRole('button',{name:'Comparar vehículos',exact:true}).click();await settle();
  assert.ok(await page.getByRole('checkbox').count()>=1);
  if(fixture){
   await page.getByRole('checkbox',{name:'Comparar QA-002',exact:true}).check();await settle();
   const table=page.locator('.fleet-comparison-table'),footer=table.locator('tfoot');
   assert.equal(await table.locator('tbody tr').count(),2);
   const parse=value=>Number(value.replace(/\./g,'').replace(',','.').replace(/[^0-9.-]/g,''));
   const distances=await table.locator('tbody tr').evaluateAll(rows=>rows.map(row=>row.cells[1].textContent));
   const summed=distances.reduce((sum,value)=>sum+parse(value),0);
   assert.ok(Math.abs(parse(await footer.locator('td').nth(0).innerText())-summed)<.002);
   const strokes=await page.locator('.recharts-line-curve').evaluateAll(nodes=>nodes.map(node=>node.getAttribute('stroke')));
   assert.equal(new Set(strokes).size,2);
   await page.getByRole('checkbox',{name:'Comparar QA-001',exact:true}).uncheck();await settle();
   assert.equal(await page.locator('.recharts-line-curve').getAttribute('stroke'),strokes[1]);
   await page.getByRole('button',{name:'Seleccionar todos',exact:true}).click();await settle();
   assert.ok((await table.locator('tbody tr').nth(2).innerText()).includes('Muestras insuficientes'));
   assert.ok((await table.locator('tbody tr').nth(2).innerText()).includes('—'));
   const download=page.waitForEvent('download');
   await page.getByRole('button',{name:'Exportar comparación CSV',exact:true}).click();
   const file=path.join(output,'comparison.csv');await(await download).saveAs(file);
   assert.ok(fs.readFileSync(file,'utf8').includes('TOTAL DISPONIBLE'));
   partial=true;await page.getByLabel('Período GPS',{exact:true}).selectOption('168');await settle();
   assert.ok((await table.locator('tbody tr').nth(1).innerText()).includes('Estadísticas actualizándose'));
   await page.getByRole('button',{name:'Actualizar pendientes o reintentar',exact:true}).click();await settle();
   assert.ok((await table.locator('tbody tr').nth(1).innerText()).includes('Consultado'));
   partial=false;denied=true;await page.getByRole('button',{name:'Actualizar datos',exact:true}).click();await settle();
   await page.getByRole('alert').filter({hasText:'Acceso revocado'}).waitFor();
   assert.ok((await table.locator('tbody tr').nth(1).innerText()).includes('—'));
   denied=false;await page.getByRole('button',{name:'Actualizar pendientes o reintentar',exact:true}).click();await settle();
   await page.getByRole('button',{name:'Limpiar selección',exact:true}).click();
   await page.getByText('Selecciona uno o más vehículos para calcular sus estadísticas.',{exact:true}).waitFor();
   assert.equal(await table.count(),0);
   await page.getByRole('button',{name:'Seleccionar todos',exact:true}).click();await settle();
  }else{
   await page.getByRole('button',{name:'Seleccionar todos',exact:true}).click();await settle();
   assert.equal(await page.locator('.fleet-comparison-table tbody tr').count(),await page.getByRole('checkbox').count());
  }
  await page.screenshot({path:path.join(output,'comparison-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(output,'comparison-mobile.png'),fullPage:true});
  if(fixture){
   restricted=true;await page.reload();await page.getByRole('button',{name:'Comparar vehículos',exact:true}).click();await settle();
   assert.equal(await page.getByRole('checkbox').count(),1);
   assert.equal(await page.getByRole('checkbox',{name:'Comparar QA-002',exact:true}).count(),0);
  }
  assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);
  console.log('FLEET_COMPARISON_OK fixture='+fixture+' read_only=True responsive=True');
 }catch(error){await page.screenshot({path:path.join(output,'comparison-failure.png'),fullPage:true});throw error;}
 finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
