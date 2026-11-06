/* Native same-origin review. No business writes or physical orders. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const proof=JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8').replace(/^\uFEFF/,''));
 const output=process.env.GPS_UI_OUTPUT;fs.mkdirSync(output,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000}});
  await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
  const page=await context.newPage(),errors=[],writes=[],raw=[];let comparison=false;
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(comparison&&new URL(r.url()).pathname.endsWith('/positions'))raw.push(r.url());});
  await page.route('**/*',async route=>{
   const r=route.request(),u=new URL(r.url());
   if(u.hostname===proof.host&&!['GET','HEAD'].includes(r.method())){
    if(u.pathname.startsWith('/web/dataset/call_kw/')&&['search_read','read','check_access_rights','load_menus'].includes(r.postDataJSON().params.method))return route.continue();
    writes.push(u.pathname);return route.abort();
   }
   return route.continue();
  });
  await page.goto('https://'+proof.host+'/tracker?asset='+encodeURIComponent(process.env.GPS_EXPECTED_ASSET||'')+'#ops');
  await page.getByRole('button',{name:'Comparar vehículos',exact:true}).click();
  await page.getByRole('button',{name:'Seleccionar todos',exact:true}).click();
  comparison=true;
  await page.getByLabel('Período GPS',{exact:true}).selectOption('720');
  await page.getByText('Calculando estadísticas de los vehículos seleccionados…',{exact:true}).waitFor({state:'hidden'});
  const result=await page.evaluate(async expected=>{
   const fleet=await(await fetch('/steps_tracker/api/fleet/snapshot',{credentials:'same-origin'})).json();
   const ids=fleet.items.map(a=>a.asset_id);if(expected&&!ids.includes(expected))throw Error('Requested real vehicle not in authorized fleet');
   const end=new Date(),start=new Date(end.getTime()-30*86400000),params=new URLSearchParams({asset_ids:ids.join(','),since:start.toISOString(),until:end.toISOString()});
   let data,elapsed,bytes,status;
   for(let i=0;i<12;i++){
    const began=performance.now(),r=await fetch('/steps_tracker/api/assets/analytics?'+params,{credentials:'same-origin'}),body=await r.text();
    elapsed=performance.now()-began;status=r.status;bytes=body.length;data=JSON.parse(body);
    if(!r.ok)throw Error('Analytics HTTP '+status);
    if(data.items.every(a=>a.complete))break;
    await new Promise(resolve=>setTimeout(resolve,5000));
   }
   return {status,elapsed_ms:elapsed,bytes,vehicles:data.items.length,complete:data.items.every(a=>a.complete),version:data.metrics_version,points:data.items.reduce((s,a)=>s+a.metrics.point_count,0)};
  },process.env.GPS_EXPECTED_ASSET||'');
  assert.equal(result.status,200);assert.equal(result.version,2);assert.ok(result.complete);assert.ok(result.vehicles>0);
  assert.equal(await page.getByRole('alert').count(),0);
  await page.screenshot({path:path.join(output,'analytics-30-days-desktop.png'),fullPage:true});
  await page.setViewportSize({width:390,height:844});
  await page.waitForFunction(()=>document.documentElement.scrollWidth<=innerWidth);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(output,'analytics-30-days-mobile.png'),fullPage:true});
  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);assert.deepEqual(raw,[]);
  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(result,null,2));
  console.log('GPS_ANALYTICS_NATIVE_OK '+JSON.stringify(result));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
