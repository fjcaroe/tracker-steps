/* Real nginx + Chromium regression, using archived 0.0.3 and 0.0.5 builds. */
const fs=require('node:fs');
const path=require('node:path');
const {execFileSync}=require('node:child_process');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');

(async()=>{
    const stage=process.argv[2],output=process.argv[3];
    assert.match(stage,/^\/opt\/steps-validation\/harvest-cache-fixture-[a-z0-9-]+$/);
    fs.mkdirSync(output,{recursive:true});
    const tool='/opt/steps-validation/harvest-cache-tools-20261126/repair_harvest_cache.py';
    const state=JSON.parse(execFileSync('ssh',['odoo-new','sudo','-n','cat',stage+'/state.json'],{encoding:'utf8'}));
    const url='http://127.0.0.1:18471/cosecha/';
    const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
    const cases=[];
    function phase(version,fixed){
        execFileSync('ssh',['odoo-new','sudo','-n','python3',tool,'fixture-switch','--stage',stage,
            '--version',version,...(fixed?['--fixed']:[])],{stdio:'pipe'});
    }
    async function policy(fixed){
        for(let i=0;i<40;i++){
            try{
                const r=await fetch(url,{cache:'no-store'});await r.arrayBuffer();
                if(r.headers.get('cache-control')===(fixed?'no-store':'no-cache'))return;
            }catch{/* A retiring nginx worker may close its keep-alive socket. */}
            await new Promise(resolve=>setTimeout(resolve,150));
        }
        throw new Error('nginx cache policy did not change');
    }
    try{
        for(const old of ['0.0.3','0.0.5']){
            phase(old,false);await policy(false);
            const context=await browser.newContext({viewport:{width:1440,height:1000}});
            const page=await context.newPage();page.setDefaultTimeout(20000);
            await page.goto(url,{waitUntil:'networkidle'});
            await page.getByText(new RegExp('Harvest '+old.replaceAll('.','\\.'))).first().waitFor();
            await page.evaluate(async()=>{await navigator.serviceWorker.ready;});
            await page.waitForFunction(()=>Boolean(navigator.serviceWorker.controller));
            await page.evaluate(async()=>{
                localStorage.setItem('steps-harvest:cache-proof:capture-v1',JSON.stringify({records:[{id:'pending-proof',synced:false}]}));
                const request=indexedDB.open('steps-harvest-cache-proof',1);
                await new Promise((resolve,reject)=>{
                    request.onupgradeneeded=()=>request.result.createObjectStore('pending');
                    request.onerror=()=>reject(request.error);
                    request.onsuccess=()=>{const db=request.result;const tx=db.transaction('pending','readwrite');
                        tx.objectStore('pending').put('preserve-this-pending','proof');
                        tx.oncomplete=()=>{db.close();resolve();};};
                });
                const other=await caches.open('other-app-cache-proof');await other.put('/other-app-proof',new Response('preserve'));
            });
            const before=await page.evaluate(()=>({...localStorage}));
            phase('0.0.11',false);await policy(false);
            await page.reload({waitUntil:'networkidle'});
            await page.getByText(new RegExp('Harvest '+old.replaceAll('.','\\.'))).first().waitFor();
            await page.screenshot({path:path.join(output,`stale-${old}.png`),fullPage:true});
            phase('0.0.11',true);await policy(true);
            await page.reload({waitUntil:'networkidle'});
            await page.getByText(/Harvest 0\.0\.11/).first().waitFor();
            assert.deepEqual(await page.evaluate(()=>({...localStorage})),before);
            const retained=await page.evaluate(async()=>{
                const value=await new Promise((resolve,reject)=>{const r=indexedDB.open('steps-harvest-cache-proof');
                    r.onerror=()=>reject(r.error);r.onsuccess=()=>{const db=r.result;
                        const get=db.transaction('pending').objectStore('pending').get('proof');
                        get.onsuccess=()=>{db.close();resolve(get.result);};};});
                const other=await (await caches.open('other-app-cache-proof')).match('/other-app-proof');
                return {pending:value,other:await other.text()};
            });
            assert.deepEqual(retained,{pending:'preserve-this-pending',other:'preserve'});
            await page.screenshot({path:path.join(output,`updated-from-${old}.png`),fullPage:true});
            cases.push({from:old,to:'0.0.11',stale_before_fix:true,storage_preserved:true,
                localStorage:true,indexedDB:true,other_app_cache:true});
            await context.close();console.log('HARVEST_BROWSER_UPGRADE_OK '+old+' -> 0.0.11');
        }
        fs.writeFileSync(path.join(output,'browser-rehearsal.json'),JSON.stringify({policy_sha256:state.policy_sha256,cases},null,2));
    }finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
