/* Decode the delivered MP4 in the browser, not just with ffmpeg. Local files only. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
(async()=>{
 const root=path.resolve(process.argv[2]),proof=JSON.parse(fs.readFileSync(path.join(root,'silent-render.json'),'utf8'));
 const chapters=JSON.parse(fs.readFileSync(path.join(root,'chapters.json'),'utf8'));
 const video=path.join(root,'Steps-Tracker-Sin-Audio.mp4');assert.ok(fs.statSync(video).size>100000);
 const server=http.createServer((req,res)=>{
  if(req.url==='/'){res.writeHead(200,{'Content-Type':'text/html; charset=utf-8'});return res.end('<!doctype html><html lang="es"><meta charset="utf-8"><title>Steps Tracker · guía visual</title><style>body{margin:0;background:#edf3e8}video{display:block;width:1280px;height:720px}</style><video id="guide" controls playsinline muted preload="auto" poster="/poster.png"><source src="/guide.mp4" type="video/mp4"></video></html>');}
  const file=req.url==='/guide.mp4'?video:req.url==='/poster.png'?path.join(root,'Steps-Tracker-Vista-Previa.png'):null;
  if(!file){res.writeHead(404);return res.end();}
  const size=fs.statSync(file).size,type=file===video?'video/mp4':'image/png',range=req.headers.range;
  if(range){const m=/^bytes=(\d+)-(\d*)$/.exec(range);if(!m){res.writeHead(416);return res.end();}const start=+m[1],end=m[2]?Math.min(+m[2],size-1):size-1;if(start>end){res.writeHead(416);return res.end();}res.writeHead(206,{'Content-Type':type,'Accept-Ranges':'bytes','Content-Range':`bytes ${start}-${end}/${size}`,'Content-Length':end-start+1});return fs.createReadStream(file,{start,end}).pipe(res);}
  res.writeHead(200,{'Content-Type':type,'Content-Length':size,'Accept-Ranges':'bytes'});fs.createReadStream(file).pipe(res);
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const browser=await chromium.launch({headless:true,channel:'msedge'}),page=await browser.newPage({viewport:{width:1280,height:720}}),stats=[];
 try{
  await page.goto('http://127.0.0.1:'+server.address().port+'/');
  await page.waitForFunction(()=>document.querySelector('video').readyState>=2);
  for(const [index,chapter] of chapters.entries()){
   const time=chapter.start-proof.source_start_trimmed+Math.min(5,(chapter.end-chapter.start)/2);
   const result=await page.evaluate(async time=>{
    const v=document.querySelector('video');if(v.error)throw new Error('Media error '+v.error.code);
    v.currentTime=time;await new Promise(r=>v.addEventListener('seeked',r,{once:true}));
    await v.play();await new Promise(r=>v.requestVideoFrameCallback?v.requestVideoFrameCallback(r):setTimeout(r,150));v.pause();
    const c=document.createElement('canvas');c.width=320;c.height=180;const x=c.getContext('2d');x.drawImage(v,0,0,320,180);
    const pixels=x.getImageData(0,0,320,150).data;let sum=0,bright=0;const colors=new Set();
    for(let i=0;i<pixels.length;i+=4){const l=(pixels[i]+pixels[i+1]+pixels[i+2])/3;sum+=l;if(l>35)bright++;colors.add((pixels[i]>>4)*256+(pixels[i+1]>>4)*16+(pixels[i+2]>>4));}
    return {time,width:v.videoWidth,height:v.videoHeight,mean:sum/(pixels.length/4),visibleFraction:bright/(pixels.length/4),colors:colors.size,error:v.error?.code||null};
   },time);
   assert.equal(result.width,1280);assert.equal(result.height,720);assert.ok(result.mean>40,'Black/dark frame');assert.ok(result.visibleFraction>.4,'Mostly black frame');assert.ok(result.colors>30,'No useful screen imagery');assert.equal(result.error,null);stats.push(result);
   if([0,2,4,7,8,10].includes(index))await page.screenshot({path:path.join(root,`browser-playback-${index.toString().padStart(2,'0')}.png`)});
  }
  fs.writeFileSync(path.join(root,'browser-playback.json'),JSON.stringify({browser:'Microsoft Edge',decodedChapters:stats.length,visibleImages:true,frames:stats},null,2));
  console.log('VIDEO_BROWSER_PLAYBACK_OK chapters='+stats.length+' visible_images=true resolution=1280x720');
 }finally{await browser.close();await new Promise(r=>server.close(r));}
})().catch(e=>{console.error(e);process.exitCode=1;});
