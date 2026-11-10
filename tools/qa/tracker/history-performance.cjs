/* Read-only native review. Session material stays on its original host. */

const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');

const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');

(async()=>{

 const proof=JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8'));

 const origin='https://'+proof.host, output=process.env.GPS_UI_OUTPUT;

 const browser=await chromium.launch({headless:true,...(process.env.GPS_BROWSER_CHANNEL?{channel:process.env.GPS_BROWSER_CHANNEL}:{})});

 try{

  const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'America/Santiago',serviceWorkers:'block'});

  await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);

  const page=await context.newPage();page.setDefaultTimeout(60000);

  const errors=[],writes=[],requests=[];let measuring=false;

  page.on('pageerror',e=>errors.push(e.message));

  await page.route(origin+'/**',route=>{

   const r=route.request();

   if(['GET','HEAD'].includes(r.method()))return route.continue();

   if(r.url().includes('/web/dataset/call_kw/')&&['read','search_read'].includes(r.postDataJSON()?.params?.method))return route.continue();

   writes.push(new URL(r.url()).pathname);return route.abort();

  });

  page.on('response',response=>{if(measuring&&response.url().includes('/positions?'))requests.push({status:response.status(),url:response.url(),at:Date.now()});});

  await page.goto(origin+'/tracker#home');

  const asset=await page.evaluate(async plate=>{const r=await(await fetch('/steps_tracker/api/fleet/snapshot')).json();const a=plate?r.items.find(a=>a.plate===plate):r.items.find(a=>a.last_position);if(!a)throw Error('No positioned asset');return a.asset_id;},process.env.GPS_EXPECTED_PLATE||null);

  measuring=true;const started=Date.now();

  await page.goto(origin+'/tracker?asset='+asset+'#history');

  await page.locator('.trail-map-canvas').waitFor();

  await page.getByRole('button',{name:'Hoy',exact:true}).waitFor({state:'visible'});

  await page.waitForFunction(()=>!document.body.innerText.includes('Consultando posiciones del período'));

  const elapsed=Date.now()-started;

  const summary=await page.locator('.tracker-history').first().textContent().catch(()=>page.locator('body').innerText());

  const samples=Number(summary.match(/(\d+) muestras GPS cargadas/)?.[1]||0);

  const native=requests.slice();measuring=false;
  const warm=[];
  for(let n=0;n<3;n++){requests.length=0;measuring=true;const t=Date.now();await page.getByRole('button',{name:'Hoy',exact:true}).click();await page.waitForFunction(()=>!document.body.innerText.includes('Consultando posiciones del período'));await page.locator('.trail-map-canvas').waitFor();measuring=false;warm.push({ms:Date.now()-t,position_requests:requests.length});}

  const from=new Date();from.setHours(0,0,0,0);

  const url=origin+'/steps_tracker/api/assets/'+asset+'/positions?limit='+(process.env.GPS_EXPECT_NEW?'5000':'500')+'&since='+encodeURIComponent(from.toISOString())+'&until='+encodeURIComponent(new Date().toISOString());

  const concurrent=await Promise.all(Array.from({length:4},async()=>{const t=Date.now();const r=await context.request.get(url);assert.equal(r.status(),200);const data=await r.json();return {ms:Date.now()-t,rows:data.items.length};}));

  if(process.env.GPS_EXPECT_NEW){assert.ok(native.length<=2,'A daily history should use at most two position pages');assert.ok((await page.locator('body').innerText()).includes('diagnóstico'));}

  const replay=page.getByRole('button',{name:'Reproducir',exact:true});

  if(await replay.isVisible()){await replay.click();await page.waitForTimeout(2000);await page.getByRole('button',{name:'Pausar',exact:true}).click().catch(()=>{});}

  fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'history-desktop.png'),fullPage:true});

  await page.setViewportSize({width:390,height:844});

  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);

  await page.screenshot({path:path.join(output,'history-mobile.png'),fullPage:true});

  assert.deepEqual(errors,[]);assert.deepEqual(writes,[]);assert.ok(native.every(r=>r.status===200));

  const report={history_ms:elapsed,warm,position_requests:native.length,samples,concurrent_reads:concurrent,browser_errors:errors.length,business_writes:writes.length};

  fs.writeFileSync(path.join(output,'result.json'),JSON.stringify(report,null,2));
  if(process.env.GPS_HISTORY_FIXTURE){
   const start=new Date();start.setHours(5,0,0,0);
   const points=[0,1,16,17].map((minutes,i)=>({id:'qa-'+i,assignment_id:'qa-link',recorded_at:new Date(start.getTime()+minutes*60000).toISOString(),received_at:new Date(start.getTime()+minutes*60000).toISOString(),lat:-33.4-i*.001,lon:-70.6,speed_kmh:30,quality:'gps',acc:null,external_power:null}));
   await page.route('**/assets/'+asset+'/positions?*',route=>route.fulfill({json:{items:points,next_cursor:null}}));
   await page.route('**/assets/'+asset+'/receiver-history?*',route=>route.fulfill({json:{items:[{at:new Date(start.getTime()+5*60000).toISOString(),contact_at:new Date(start.getTime()+5*60000).toISOString(),fix_at:null,assignment_id:'qa-link',state:'no_gps',pending:0}],partial:false}}));
   await page.getByRole('button',{name:'Hoy',exact:true}).click();
   await page.locator('.trail-gap-summary').getByText('Hubo comunicación. El equipo informó falta de posición GPS válida.').waitFor();
   assert.ok(await page.getByText('Naranja discontinuo · intervalo desconocido, sin ruta ni distancia atribuida').isVisible());
   await page.screenshot({path:path.join(output,'diagnostic-fixture.png'),fullPage:true});
  }
  console.log('HISTORY_NATIVE_OK '+JSON.stringify(report));

 }finally{await browser.close();}

})().catch(e=>{console.error(e.message);process.exitCode=1;});

