/* Login form + native auth contract. Fixture mode intercepts all business requests. */
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [mode,requestedOrigin,dist,out,accessFile]=process.argv.slice(2);fs.mkdirSync(out,{recursive:true});let origin=requestedOrigin,server;
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,serviceWorkers:'block'}),page=await context.newPage();
  let state='anonymous',scenario='wrong',posts=0;
  if(mode==='fixture'){
   // A real local HTTP server exercises native redirect chains (route mocks
   // only intercept the first request in a browser's redirected fetch).
   server=require('http').createServer(async(req,res)=>{
    const url=new URL(req.url,origin),method=req.method;let posted='';for await(const chunk of req)posted+=chunk;
    const route={abort:()=>{res.writeHead(404);res.end();},fulfill:({status=200,headers={},contentType,body='',path:file})=>{if(file){body=fs.readFileSync(file);contentType=file.endsWith('.js')?'application/javascript':file.endsWith('.css')?'text/css':file.endsWith('.svg')?'image/svg+xml':'text/html';}res.writeHead(status,{...headers,...(contentType?{'content-type':contentType}:{})});res.end(body);}};
    if(url.pathname==='/steps_tracker/context')return state==='anonymous'?route.fulfill({status:303,headers:{location:'/web/login'}}):route.fulfill({status:403,body:'Not authorized'});
    if(url.pathname==='/web/login'&&method==='GET')return route.fulfill({contentType:'text/html',body:'<form><input name="csrf_token" value="native-csrf"></form>'});
    if(url.pathname==='/web/login'&&method==='POST'){
     const form=new URLSearchParams(posted);assert.equal(form.get('csrf_token'),'native-csrf');assert.equal(form.get('login'),'qa@example.invalid');assert.equal(form.get('password'),'fixture-only');assert.equal(form.get('redirect'),'/tracker?company=2#protection');posts++;
     if(scenario==='offline')return route.fulfill({status:503,body:'Unavailable'});
     if(scenario==='mfa')return route.fulfill({status:303,headers:{location:'/web/login/totp?redirect=%2Ftracker'}});
     return route.fulfill({contentType:'text/html',body:'<form class="oe_login_form"><p class="alert-danger">Wrong login/password</p></form>'});
    }
    if(url.pathname.startsWith('/web/login/totp'))return route.fulfill({contentType:'text/html',body:'<h1>Native MFA</h1>'});
    let file=url.pathname==='/tracker'?path.join(dist,'index.html'):path.join(dist,url.pathname.replace(/^\/web_tracker\//,''));
    if(fs.existsSync(file)&&fs.statSync(file).isFile())return route.fulfill({path:file});
    return route.abort();
   });await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));origin='http://127.0.0.1:'+server.address().port;
   await page.route('**/*',route=>new URL(route.request().url()).origin===origin?route.continue():route.abort());
  }
  await page.goto(origin+'/tracker?company=2#protection');await page.getByRole('heading',{name:'Todo bajo control.'}).waitFor();
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.screenshot({path:path.join(out,'login-mobile.png'),fullPage:true});await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:path.join(out,'login-desktop.png'),fullPage:true});await page.setViewportSize({width:390,height:844});
  await page.getByLabel('Correo o usuario',{exact:true}).fill(mode==='fixture'?'qa@example.invalid':'tracker-qa-not-an-account@example.invalid');await page.getByLabel('Contraseña',{exact:true}).fill(mode==='fixture'?'fixture-only':'invalid-login-qa');
  await page.getByRole('button',{name:'Mostrar contraseña',exact:true}).click();assert.equal(await page.locator('#tracker-password').getAttribute('type'),'text');await page.getByRole('button',{name:'Ocultar contraseña',exact:true}).click();
  await page.getByRole('button',{name:'Entrar a mi Tracker',exact:true}).click();await page.getByRole('alert').filter({hasText:'no coinciden'}).waitFor();assert(new URL(page.url()).pathname==='/tracker');
  if(mode==='fixture'){
   scenario='offline';await page.getByRole('button',{name:'Entrar a mi Tracker',exact:true}).click();await page.getByRole('alert').filter({hasText:'no está disponible'}).waitFor();
   scenario='mfa';await page.getByRole('button',{name:'Entrar a mi Tracker',exact:true}).click();await page.getByRole('heading',{name:'Native MFA'}).waitFor();assert.equal(posts,3);
  }else if(accessFile){
   // Existing private preview account; never print/store the password or a trace.
   const codes=[...fs.readFileSync(accessFile,'utf8').matchAll(/<code>(.*?)<\/code>/g)].map(m=>m[1]);assert(codes.length===2);
   await page.getByLabel('Correo o usuario',{exact:true}).fill(codes[0]);
   await page.getByLabel('Contraseña',{exact:true}).fill(codes[1]);await page.getByRole('button',{name:'Entrar a mi Tracker',exact:true}).click();await page.getByRole('navigation',{name:'Mi Tracker',exact:true}).waitFor();
   const scoped=await page.evaluate(async()=>{const r=await fetch('/steps_tracker/api/fleet/snapshot');return r.json();});assert.equal(scoped.total,1);
   await page.screenshot({path:path.join(out,'authenticated-mobile.png'),fullPage:true});await page.getByRole('link',{name:'Cerrar sesión'}).click();await page.getByRole('heading',{name:'Todo bajo control.'}).waitFor();
  }
  fs.writeFileSync(path.join(out,'proof.json'),JSON.stringify({mode,responsive:true,native_csrf:true,invalid_login_inline:true,mfa:mode==='fixture',real_preview_login:!!accessFile,logout:!!accessFile}));console.log('TRACKER_ENTRY_BROWSER_OK mode='+mode);
 }finally{await browser.close();if(server)server.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
