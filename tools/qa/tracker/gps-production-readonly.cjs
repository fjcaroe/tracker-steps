/* Existing user's temporary Odoo session; open and inspect, never save a GPS. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const proof=JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8').replace(/^\uFEFF/,''));
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1365,height:1000}});
 await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
 const page=await context.newPage();const errors=[];const writes=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&r.url().includes('/steps_tracker/'))writes.push(r.url());});
 const output=process.env.GPS_UI_OUTPUT;fs.mkdirSync(output,{recursive:true});
 try{
  await page.goto('https://'+proof.host+'/web_tracker/#settings');
  await page.getByRole('heading',{name:'GPS y conectividad',exact:true}).waitFor();
  if(proof.host.startsWith('cerro')){await page.getByRole('heading',{name:'Preparar los equipos Coban'}).waitFor();await page.getByText('Receptor disponible',{exact:true}).waitFor();}
  await page.getByRole('button',{name:'Agregar GPS',exact:true}).click();
  const dialog=page.getByRole('dialog');await dialog.waitFor();
  for(const name of ['IMEI (15 dígitos)','Marca','Modelo','Número de la SIM','APN confirmado por el operador','Próxima recarga','Vencimiento bolsa de datos'])await dialog.getByLabel(name,{exact:true}).waitFor();
  assert.equal(await dialog.getByLabel('Operador',{exact:true}).inputValue(),'Entel');
  await page.screenshot({path:path.join(output,'gps-form-desktop.png'),fullPage:true});
  await dialog.getByRole('button',{name:'Cancelar',exact:true}).click();
  for(const width of [1365,390]){await page.setViewportSize({width,height:1000});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(output,'gps-live-'+width+'.png'),fullPage:true});}
  if(process.env.TRACKER_REVIEW_OPERATION==='1'){
   await page.setViewportSize({width:1365,height:1000});
   await page.getByRole('button',{name:'Operación',exact:true}).click();
   const nav=page.getByRole('navigation',{name:'Navegación principal'});await nav.waitFor();
   await nav.getByRole('button',{name:'Registro',exact:true}).click();
   await page.getByRole('heading',{name:'Registro de operación',exact:true}).waitFor();
   await page.getByRole('button',{name:'Iniciar recorrido',exact:true}).waitFor();
   await page.getByRole('combobox',{name:/^Máquina/}).waitFor();
   const catalogue=await page.evaluate(async()=>{
    const response=await fetch('https://stepsapp.cl/tracker-steps/machines',{headers:{Authorization:'Bearer '+localStorage.getItem('tracker_token')}});
    return {status:response.status,list:Array.isArray(await response.json())};
   });
   assert.deepEqual(catalogue,{status:200,list:true});
   await page.screenshot({path:path.join(output,'operation-native.png'),fullPage:true});
   await nav.getByRole('button',{name:'← Flota y GPS',exact:true}).click();
   await page.getByRole('button',{name:'Configuración',exact:true}).click();
   await page.getByRole('heading',{name:'Preparar los equipos Coban'}).waitFor();
  }
  assert.deepEqual(writes.filter(url=>!url.endsWith('/steps_tracker/classic-session')),[]);assert.deepEqual(errors,[]);
  console.log('GPS_NATIVE_BROWSER_OK host='+proof.host+' authenticated=true form=true receiver_status=true responsive=true business_writes=0 operation_review='+String(process.env.TRACKER_REVIEW_OPERATION==='1'));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
