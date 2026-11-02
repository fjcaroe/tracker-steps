/* Served Development build + real HTTP/ORM on a private database over SSH.
   All /tracker-dev-api requests are intercepted to the disposable copy.
   The live production API cannot receive any fixture write. */
const fs=require('fs');
const path=require('path');
const { chromium }=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
(async()=>{
 const [proofFile,out]=process.argv.slice(2);if(!proofFile||!out)throw Error('Pass private proof JSON and artifact directory');
 const proof=JSON.parse(fs.readFileSync(proofFile,'utf8'));fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},timezoneId:'America/Santiago',serviceWorkers:'block'});
  const page=await context.newPage();let network=true,posts=0,gps=0;
  await page.addInitScript(({token})=>{localStorage.setItem('steps_movil_token',token);localStorage.setItem('steps_movil_settings',JSON.stringify({seenHelp:true}));},proof);
  await page.route('**/tracker-dev-api/**',async route=>{
   if(!network)return route.abort('internetdisconnected');
   const req=route.request();const url='http://127.0.0.1:18012/'+new URL(req.url()).pathname.split('/tracker-dev-api/')[1]+new URL(req.url()).search;
   if(req.method()==='POST'&&url.includes('/events'))posts++;
   const response=await context.request.fetch(url,{method:req.method(),headers:{authorization:'Bearer '+proof.token,'content-type':'application/json'},data:req.postData()||undefined});
   return route.fulfill({response});
  });
  page.on('request',req=>{if(req.method()==='POST'&&req.url().includes('/tracker-steps/'))throw Error('A fixture write reached the production API');});
  await page.addInitScript(()=>{navigator.geolocation.watchPosition=()=>{window.__unexpectedGps=(window.__unexpectedGps||0)+1;return 1;};});
  await page.goto('https://desarrollo.stepsapp.cl/truck/');
  await page.getByRole('button',{name:'Hoy',exact:true}).click();
  await page.getByRole('heading',{name:'Servicio de copia',exact:true}).waitFor();
  const card=page.locator('.passenger-service');
  if(!(await card.getByRole('button',{name:'Registrar subida'}).first().isDisabled()))throw Error('Boarding enabled without explicit preparation');
  await page.getByRole('button',{name:'Preparar servicio en este teléfono'}).click();
  await page.getByText('Preparado hasta',{exact:false}).waitFor();
  await card.screenshot({path:path.join(out,'prepared-390.png')});
  network=false;
  await page.evaluate(()=>{Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>false});window.dispatchEvent(new Event('offline'));});
  await page.getByText('Sin señal. Solo puedes operar',{exact:false}).waitFor();
  const person=n=>card.locator('li').filter({has:page.getByText('Pasajero ficticio '+n,{exact:true})});
  for(const n of [1,2]){await person(n).getByRole('button',{name:'Registrar subida'}).click();await person(n).getByText('A bordo',{exact:true}).waitFor();}
  page.once('dialog',dialog=>dialog.accept());await person(3).getByRole('button',{name:'Marcar ausente'}).click();await person(3).getByText('Ausente',{exact:true}).waitFor();
  for(const n of [1,2]){await person(n).getByRole('button',{name:'Registrar bajada'}).click();await person(n).getByText('Descendió',{exact:true}).waitFor();}
  if(posts!==0)throw Error('Offline actions attempted to write before reconnect');
  await page.getByLabel('Mostrar',{exact:false}).selectOption('no_show');await person(3).waitFor();if(await person(1).count())throw Error('State filter failed');
  await page.getByLabel('Mostrar',{exact:false}).selectOption('all');
  await card.screenshot({path:path.join(out,'offline-complete-390.png')});
  // Component remount proves storage survives leaving Hoy, without a new login.
  await page.getByRole('button',{name:'Perfil',exact:true}).click();await page.getByText('Versión 1.6.1 · 5 elementos por enviar',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Hoy',exact:true}).click();await person(1).getByText('Descendió',{exact:true}).waitFor();
  network=true;await page.evaluate(()=>{Object.defineProperty(navigator,'onLine',{configurable:true,get:()=>true});window.dispatchEvent(new Event('online'));});
  await person(1).getByText('Confirmado',{exact:false}).waitFor();
  const response=await context.request.get('http://127.0.0.1:18012/mobile/services/'+proof.service.id+'/manifest',{headers:{authorization:'Bearer '+proof.token}});const final=await response.json();
  if(final.manifest_version!==5||final.occupied!==0||final.events.length!==5)throw Error('Final manifest does not match complete offline service');
  await page.getByText('Leer QR o ingresar código',{exact:true}).click();
  await page.getByLabel('Código del pasajero',{exact:true}).fill('steps:passenger:'+proof.service.passengers[1].id);
  await page.getByRole('button',{name:'Buscar código',exact:true}).click();await person(2).waitFor();if(await person(1).count())throw Error('Code did not select correct passenger');
  await page.getByRole('button',{name:'Abrir cámara',exact:true}).click();await page.getByRole('button',{name:'Cerrar cámara',exact:true}).waitFor();await page.getByRole('button',{name:'Cerrar cámara',exact:true}).click();
  await page.getByLabel('Buscar pasajero',{exact:true}).fill('');
  if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Horizontal overflow');
  gps=await page.evaluate(()=>window.__unexpectedGps||0);if(gps)throw Error('Location requested without opt-in');
  await card.screenshot({path:path.join(out,'synced-390.png')});
  await page.setViewportSize({width:1440,height:1000});await card.screenshot({path:path.join(out,'synced-desktop.png')});
  console.log('PASSENGER_BOARDING_UI_OK served_development=True private_postgres=True offline_service=True final_manifest=5 duplicate_receipts=0 filters=True code_lookup=True no_implicit_gps=True production_fixture_writes=0');
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
