/* Native layout acceptance. Uses an ephemeral existing-user session; never saves business data. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const proof=JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8').replace(/^\uFEFF/,''));
 assert.ok(['desarrollo.stepsapp.cl','cerroelplomo.stepsapp.cl'].includes(proof.host));
 const browser=await chromium.launch({headless:true,channel:'msedge'}),context=await browser.newContext({viewport:{width:1440,height:1000}});
 await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
 const page=await context.newPage(),errors=[],mutations=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{const r=route.request();if(new URL(r.url()).hostname===proof.host&&r.method()!=='GET'&&r.method()!=='HEAD'){mutations.push(new URL(r.url()).pathname);return route.abort();}return route.continue();});
 const output=process.env.GPS_UI_OUTPUT;fs.mkdirSync(output,{recursive:true});
 try{
  await page.goto('https://'+proof.host+'/web_tracker/#live');
  await page.locator('.fleet-card').first().click();
  const inspector=page.locator('.inspector');await inspector.waitFor();
  assert.equal(await inspector.getByRole('tab',{name:'Resumen',exact:true}).getAttribute('aria-selected'),'true');
  assert.equal(await inspector.locator('input[type=date]').count(),0);
  await page.waitForTimeout(2200);
  let map=await page.locator('.fleet-map').boundingBox(),detail=await inspector.boundingBox();
  assert.ok(map&&detail&&Math.abs(map.height-detail.height)<3,'Map and inspector have equal height');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(output,'desktop-summary.png'),fullPage:true});
  await inspector.getByRole('tab',{name:'Equipo GPS',exact:true}).click();await inspector.getByText('Contacto ACC',{exact:true}).waitFor();
  assert.equal(await inspector.getByRole('button',{name:'Editar ficha',exact:true}).count(),1);
  await inspector.getByRole('tab',{name:'Equipo GPS',exact:true}).press('ArrowRight');
  assert.equal(await inspector.getByRole('tab',{name:'Costos',exact:true}).getAttribute('aria-selected'),'true');
  assert.equal(await inspector.locator('input[type=date]').count(),2);
  detail=await inspector.boundingBox();assert.ok(Math.abs(map.height-detail.height)<3);
  await page.screenshot({path:path.join(output,'desktop-costs.png'),fullPage:true});
  await inspector.getByRole('tab',{name:'Resumen',exact:true}).click();
  await inspector.getByRole('button',{name:'Ver historial de posiciones'}).click();await page.getByRole('dialog').waitFor();
  await page.getByRole('dialog').getByRole('button',{name:'Cerrar',exact:true}).click();
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(700);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await inspector.getByRole('tab',{name:'Equipo GPS',exact:true}).click();
  await page.screenshot({path:path.join(output,'mobile-gps.png'),fullPage:true});
  assert.deepEqual(mutations,[]);assert.deepEqual(errors,[]);
  console.log('WEB_MONITOR_LAYOUT_OK equal_panes=True tabs=True keyboard=True costs_preserved=True history=True mobile=True business_writes=0');
 }catch(e){await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
