/* Browser-only synthetic fixtures never enter production storage. Google Routes is real. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const proof=JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8').replace(/^\uFEFF/,''));
 assert.ok(['desarrollo.stepsapp.cl','cerroelplomo.stepsapp.cl'].includes(proof.host));
 const fixture=process.env.GPS_ROUTE_FIXTURE==='1',output=process.env.GPS_UI_OUTPUT;
 const browser=await chromium.launch({headless:true,channel:'msedge'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
 const page=await context.newPage(),errors=[],mutations=[];let reads=0,denied=false;
 const start=Date.now()-3600000;
 let samples=Array.from({length:19},(_,i)=>{const n=Math.min(i,8);return {id:'route-qa-'+i,recorded_at:new Date(start+(i<14?i:i+20)*60000).toISOString(),received_at:new Date(start+(i<14?i:i+20)*60000).toISOString(),lat:i<14?-33.4295-n*.0008:-33.446+i*.0004,lon:i<14?-70.6184+n*.00002:-70.618+i*.0001,speed_kmh:i>=9&&i<14?0:30,quality:'gps',acc:null,external_power:null};});
 await page.addInitScript(()=>{window.phoneCalls=0;Object.defineProperty(navigator,'geolocation',{value:{getCurrentPosition:()=>{window.phoneCalls++;},watchPosition:()=>{window.phoneCalls++;return 1;},clearWatch:()=>{}}});});
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{const request=route.request(),url=new URL(request.url());
  if(url.hostname===proof.host&&!['GET','HEAD'].includes(request.method())){mutations.push(url.pathname);return route.abort();}
  if(process.env.GPS_ROUTE_DIST&&url.hostname===proof.host&&url.pathname.startsWith('/web_tracker/')){const root=path.resolve(process.env.GPS_ROUTE_DIST),file=path.resolve(root,url.pathname.slice('/web_tracker/'.length)||'index.html');assert.ok(file.startsWith(root+path.sep));return route.fulfill({status:200,contentType:({'.js':'application/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});}
  if(fixture&&url.pathname.endsWith('/fleet/snapshot'))return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({items:[{asset_id:'00000000-0000-4000-8000-000000000101',name:'Vehículo de prueba',plate:'QA-001',type:'car',created_at:new Date(start).toISOString(),last_position:samples.at(-1),signal_state:'received',motion_state:'moving',position_stale:false,protection_state:'disarmed',capabilities:{tracking:'approved',remote_start_inhibit:'not_approved'},device:{brand:'Coban',model:'401',protocol:'gps103-ascii'}}],total:1,next_cursor:null})});
  if(fixture&&url.pathname.match(/\/assets\/[^/]+\/positions$/)){
   reads++;const older=url.searchParams.has('before');return route.fulfill({status:denied?403:200,contentType:'application/json',body:JSON.stringify(denied?{detail:'QA revoked'}:{items:(older?samples.slice(0,9):samples.slice(9)).reverse(),next_cursor:older?null:'qa-page'})});
  }
  return route.continue();
 });
 fs.mkdirSync(output,{recursive:true});
 try{
  await page.goto('https://'+proof.host+'/web_tracker/'+(process.env.GPS_REVIEW_ASSET?'?asset='+encodeURIComponent(process.env.GPS_REVIEW_ASSET):'')+'#live');await page.locator(process.env.GPS_REVIEW_ASSET?'.fleet-card.is-selected':'.fleet-card').first().click();
  if(fixture){await page.waitForFunction(()=>window.google?.maps?.importLibrary);const reference=await page.evaluate(async()=>{const {Route}=await google.maps.importLibrary('routes');const {routes}=await Route.computeRoutes({origin:{lat:-33.4295,lng:-70.6184},destination:{lat:-33.4359,lng:-70.61824},travelMode:'DRIVING',fields:['path']});return routes[0].path.map(p=>typeof p.toJSON==='function'?p.toJSON():p);});assert.ok(reference.length>8);samples=samples.map((p,i)=>{const at=reference[Math.round(Math.min(i,8)*(reference.length-1)/8)];const back=reference[Math.round((i-14)*(reference.length-1)/4)];return i<14?{...p,lat:at.lat,lon:at.lng}:{...p,lat:back.lat,lon:back.lng};});}
  await page.getByRole('button',{name:'Ver historial de posiciones',exact:true}).click();
  const dialog=page.getByRole('dialog');await dialog.getByRole('button',{name:'Reproducir',exact:true}).waitFor({timeout:45000});
  await dialog.locator('.trail-map-canvas .gm-style').first().waitFor();
  if(fixture){assert.equal(reads,2);assert.equal(await dialog.locator('.trail-stats>div').last().locator('strong').innerText(),'19');await dialog.getByText(/cortes o saltos/).waitFor();}
  assert.equal(await dialog.getByLabel('Tramo para aproximar',{exact:true}).count(),0);
  if(fixture){
   const distance=await dialog.locator('.trail-stats>div').first().innerText();
   await dialog.getByLabel('Duración mínima de parada',{exact:true}).selectOption('3');assert.equal(await dialog.locator('.trail-stats>div').nth(2).locator('strong').innerText(),'1');
   await dialog.getByLabel('Duración mínima de parada',{exact:true}).selectOption('10');assert.equal(await dialog.locator('.trail-stats>div').nth(2).locator('strong').innerText(),'0');assert.equal(await dialog.locator('.trail-stats>div').first().innerText(),distance);
   await dialog.getByLabel('Mostrar paradas',{exact:true}).uncheck();await dialog.getByLabel('Mostrar paradas',{exact:true}).check();await dialog.getByLabel('Seguir reproducción',{exact:true}).check();
   const download=page.waitForEvent('download');await dialog.getByRole('button',{name:'Descargar GPX',exact:true}).click();const file=await (await download).path();const gpx=fs.readFileSync(file,'utf8');assert.ok(gpx.includes('<trkseg>'));assert.ok((gpx.match(/<trkseg>/g)||[]).length>1);assert.ok(gpx.includes('creator="Steps Tracker"'));
  }
  await dialog.getByRole('button',{name:'Reproducir',exact:true}).click();await dialog.getByRole('button',{name:'Pausar',exact:true}).waitFor();await page.waitForTimeout(1000);await dialog.getByRole('button',{name:'Pausar',exact:true}).click();
  assert.ok(Number(await dialog.getByRole('slider',{name:'Posición en el recorrido'}).inputValue())>0);
  if(fixture){await dialog.getByRole('button',{name:'Aproximar por calles',exact:true}).click();await Promise.race([dialog.getByText('Azul: estimación por calles, no recorrido comprobado.',{exact:true}).waitFor({timeout:45000}),dialog.locator('.trail-map-notice').waitFor().then(async()=>{throw new Error(await dialog.locator('.trail-map-notice').innerText());})]);}
  await page.waitForTimeout(2000);await page.screenshot({path:path.join(output,'desktop-route.png'),fullPage:true});
  assert.equal(await dialog.evaluate(e=>e.scrollWidth>e.clientWidth),false);
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(600);assert.equal(await dialog.evaluate(e=>e.scrollWidth>e.clientWidth),false);await page.screenshot({path:path.join(output,'mobile-route.png'),fullPage:true});
  if(fixture){await dialog.getByText('Elegir fechas',{exact:true}).click();await dialog.getByLabel('Desde',{exact:true}).fill('2020-01-01T00:00');await dialog.getByLabel('Hasta',{exact:true}).fill('2020-01-02T00:00');await dialog.getByRole('button',{name:'Ver recorrido',exact:true}).click();await dialog.getByText('No hay posiciones en este período. Prueba con otro rango.',{exact:true}).waitFor();assert.equal(await dialog.locator('.trail-map-canvas').count(),0);await dialog.getByRole('button',{name:'Últimas 24 h',exact:true}).click();await dialog.getByRole('button',{name:'Reproducir',exact:true}).waitFor();denied=true;await dialog.getByRole('button',{name:'Últimas 2 h',exact:true}).click();await dialog.getByRole('alert').waitFor();assert.equal(await dialog.locator('.trail-map-canvas').count(),0);}
  assert.deepEqual(errors,[]);assert.deepEqual(mutations,[]);assert.equal(await page.evaluate(()=>window.phoneCalls),0);
  await dialog.getByRole('button',{name:'Cerrar',exact:true}).click();assert.equal(await page.getByRole('dialog').count(),0);
  console.log('ROUTE_HISTORY_NATIVE_OK fixture='+fixture+' pagination=True map=True playback=True road_approximation='+fixture+' revoked_clear='+fixture+' mobile=True business_writes=0');
 }catch(e){await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
