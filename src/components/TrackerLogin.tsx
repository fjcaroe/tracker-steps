import {useState, type FormEvent} from 'react';
import TrackerIcon from './TrackerIcon';
import './TrackerLogin.css';

/** Use Odoo's own CSRF-protected login, including its MFA continuation. */
export default function TrackerLogin({accessError=''}:{accessError?:string}) {
 const [login,setLogin]=useState(''),[password,setPassword]=useState(''),[visible,setVisible]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const query=new URLSearchParams(window.location.search);
 const jornada=query.get('entrada')==='jornada';
 if(jornada)query.delete('entrada');
 const destination=(jornada?'/tracker/jornada/':'/tracker')+(query.size?'?'+query.toString():'')+window.location.hash;
 const enter=()=>{setPassword('');window.history.replaceState(window.history.state,'',destination);window.location.reload();};
 const submit=async(event:FormEvent<HTMLFormElement>)=>{
  event.preventDefault();if(busy)return;setBusy(true);setError('');
  try{
   const bootstrap=await fetch('/web/login',{credentials:'same-origin',cache:'no-store'});
   if(!bootstrap.ok)throw Error('El acceso no está disponible. Inténtalo nuevamente en unos momentos.');
   const doc=new DOMParser().parseFromString(await bootstrap.text(),'text/html');
   const token=doc.querySelector<HTMLInputElement>('input[name="csrf_token"]')?.value;
   if(!token)throw Error('No pudimos preparar una conexión segura. Recarga la página para intentar nuevamente.');
   const body=new URLSearchParams({csrf_token:token,login:login.trim(),password,type:'password',redirect:destination});
   const db=doc.querySelector<HTMLInputElement>('input[name="db"]')?.value;if(db)body.set('db',db);
   const result=await fetch('/web/login',{method:'POST',credentials:'same-origin',body,cache:'no-store'});
   const url=new URL(result.url);
   if(url.origin!==window.location.origin)throw Error('No fue posible completar el acceso en este sitio.');
   // Preserve native two-factor authentication and any installed login challenge.
   if(url.pathname.startsWith('/web/login/')){setPassword('');window.location.assign(url.href);return;}
   if(url.pathname==='/tracker'||url.pathname==='/tracker/jornada/')document.cookie='cids=; Max-Age=0; Path=/; Secure; SameSite=Lax';
   const context=await fetch('/steps_tracker/context',{credentials:'same-origin',redirect:'manual',cache:'no-store',headers:{Accept:'application/json'}});
   if(context.ok&&context.headers.get('content-type')?.includes('application/json')){enter();return;}
   if(context.status===403){enter();return;}
   if(!result.ok&&result.status!==400)throw Error('El acceso no está disponible. Inténtalo nuevamente en unos momentos.');
   setError('El correo o la contraseña no coinciden. Revisa los datos e inténtalo otra vez.');
  }catch(e){setError((e as Error).message);}
  finally{setBusy(false);}
 };
 return <main className="tracker-access">
  <section className="tracker-access-story" aria-label="Steps Tracker">
   <a className="tracker-access-brand" href="/tracker"><b><TrackerIcon name="live" size={28}/></b><span>Steps <strong>Tracker</strong></span></a>
   <div className="tracker-access-intro"><span className="tracker-access-eyebrow">TU VEHÍCULO. TU TRANQUILIDAD.</span><h1>Siempre cerca.<br/><em>Vayas donde vayas.</em></h1><p>Ubicación, recorridos y protección de tus vehículos, en un solo lugar.</p>
    <div className="tracker-access-route" aria-hidden="true"><svg viewBox="0 0 480 190" fill="none"><path className="access-street" d="M0 46h150v100h180V20h150M60 0v190M0 96h480M235 0v190M405 0v190"/><path className="access-route" d="M60 146h90V96h180V46h75"/><circle cx="60" cy="146" r="9"/><circle cx="405" cy="46" r="12"/></svg><span><i/> Tu camino, conectado</span></div>
    <ul><li><TrackerIcon name="live"/>Ubicación en el mapa</li><li><TrackerIcon name="history"/>Historial de recorridos</li><li><TrackerIcon name="protection"/>Protección y control</li></ul>
   </div><small>GPS · Movilidad · Protección</small>
  </section>
  <section className="tracker-access-panel"><div className="tracker-access-form"><span className="tracker-access-eyebrow">BIENVENIDO A TU TRACKER</span><h2>Todo bajo control.</h2><p>Entra para ver tus vehículos y seguir su recorrido.</p>
   {accessError?<div className="tracker-access-denied"><p role="alert">{accessError}</p><p>Solicita al administrador que revise tu acceso a Tracker y la compañía asignada.</p><a href="/web/session/logout?redirect=/tracker">Entrar con otra cuenta</a></div>:<form onSubmit={event=>void submit(event)} aria-label="Iniciar sesión en Tracker">
    <label htmlFor="tracker-email">Correo o usuario</label><input id="tracker-email" name="login" type="text" inputMode="email" autoComplete="username" autoCapitalize="none" spellCheck={false} placeholder="tu@correo.cl" required value={login} onChange={e=>setLogin(e.target.value)} disabled={busy}/>
    <label htmlFor="tracker-password">Contraseña</label><div className="tracker-access-password"><input id="tracker-password" name="password" type={visible?'text':'password'} autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)} disabled={busy}/><button type="button" aria-label={visible?'Ocultar contraseña':'Mostrar contraseña'} aria-pressed={visible} onClick={()=>setVisible(v=>!v)}>{visible?'Ocultar':'Mostrar'}</button></div>
    {error&&<p className="tracker-access-error" role="alert">{error}</p>}
    <button className="tracker-access-submit" type="submit" disabled={busy}>{busy?'Iniciando sesión…':'Entrar a mi Tracker'}{!busy&&<TrackerIcon name="arrow" size={20}/>}</button>
    <p className="tracker-access-help">Usa la cuenta que te asignó tu administrador. Si necesitas recuperar el acceso, comunícate con él.</p>
   </form>}
   <footer><TrackerIcon name="protection" size={17}/><span>Acceso personal · Solo los vehículos autorizados</span></footer>
  </div></section>
 </main>;
}
