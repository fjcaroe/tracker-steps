/* Read the actual HTTPS Harvest configuration in all three authorized hosts. */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');
(async()=>{
    const input=process.argv[2],output=process.argv[3];
    const expected=process.argv[4] || '0.0.11';
    assert.ok(['0.0.11','0.0.12'].includes(expected));
    fs.mkdirSync(output,{recursive:true});
    const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
    const result=[];
    try{
        for(const environment of ['development','qa-cerro','cerro']){
            const proof=JSON.parse(fs.readFileSync(path.join(input,environment+'.json'),'utf8'));
            assert.ok(['desarrollo.stepsapp.cl','qa-cerroelplomo.stepsapp.cl','cerroelplomo.stepsapp.cl'].includes(proof.host));
            const context=await browser.newContext({viewport:{width:1440,height:1000},locale:'es-CL'});
            await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true},
                {name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
            const page=await context.newPage();page.setDefaultTimeout(25000);
            const errors=[];page.on('pageerror',error=>errors.push(error.message));
            await page.route('**/*',async route=>{
                const request=route.request(),url=new URL(request.url());
                if(request.method()!=='GET' && url.pathname!=='/web/session/get_session_info')
                    throw new Error('Unexpected live business write: '+url.pathname);
                await route.continue();
            });
            const response=await page.goto('https://'+proof.host+'/cosecha/',{waitUntil:'domcontentloaded',timeout:90000});
            assert.equal(response.status(),200);assert.equal(response.headers()['cache-control'],'no-store');
            await page.locator('.environment-label').filter({hasText:'Harvest '+expected}).waitFor();
            await page.getByRole('button',{name:'Configuración',exact:true}).first().click();
            await page.getByRole('heading',{name:'Configuración de cosecha',exact:true}).waitFor();
            await page.getByRole('button',{name:'Sin tarja',exact:true}).waitFor();
            await page.getByRole('button',{name:'Peso estándar',exact:true}).waitFor();
            await page.screenshot({path:path.join(output,environment+'.png'),fullPage:true});
            if(expected==='0.0.12'){
                await page.getByRole('navigation',{name:'Navegación principal',exact:true}).getByRole('button',{name:'Jornadas',exact:true}).click();
                await page.getByRole('button',{name:'Nueva OT',exact:true}).click();
                const form=page.getByRole('dialog',{name:'Nueva orden de trabajo',exact:true});
                for(const field of ['operationLocation','passNumber','harvestType']) assert.equal(await form.locator(`[name=${field}]`).count(),1);
                assert.equal(await form.locator('[name=passNumber]').evaluate(input=>input.required),true);
                await page.screenshot({path:path.join(output,environment+'-new-ot.png')});
                await form.getByRole('button',{name:'Cancelar',exact:true}).click();
            }
            assert.deepEqual(errors,[]);
            result.push({environment,host:proof.host,version:expected,configuration:true,withoutTarja:true,
                         standardWeight:true,businessWrites:0,errors});
            await context.close();
        }
        fs.writeFileSync(path.join(output,'live-versions.json'),JSON.stringify(result,null,2));
        console.log('HARVEST_LIVE_VERSIONS_OK '+JSON.stringify(result));
    }finally{await browser.close();}
})().catch(error=>{console.error(error.stack);process.exitCode=1;});
