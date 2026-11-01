import {useEffect,useState} from 'react';
import {odooCall} from '../services/odooOperations';
import type {FleetContext} from '../services/fleetApi';
import './TrackerCompanySelector.css';
type Company={id:number;name:string};
export default function TrackerCompanySelector({context}:{context:FleetContext}){
 const [companies,setCompanies]=useState<Company[]>([]),[error,setError]=useState('');
 const switchCompany=(id:number,allowed:Company[])=>{
  if(!allowed.some(c=>c.id===id)){setError('Esta compañía no está disponible con tu usuario.');return;}
  if(id===context.company_id)return;
  document.cookie=`cids=${id}; Path=/; Max-Age=31536000; SameSite=Lax; Secure`;
  const url=new URL(window.location.href);url.searchParams.delete('asset');url.searchParams.delete('company');window.history.replaceState(window.history.state,'',url);window.location.reload();
 };
 useEffect(()=>{let active=true;
  (async()=>{try{
   const users=await odooCall<{company_ids:number[]}[]>(context,'res.users','read',[[context.user_id]],{fields:['company_ids']});
   const allowed=users[0]?.company_ids||[];
   const rows=await odooCall<Company[]>(context,'res.company','search_read',[],{domain:[['id','in',allowed]],fields:['id','name'],order:'name',limit:501});
   if(!active)return;setCompanies(rows);
   const requested=new URLSearchParams(window.location.search).get('company');
   if(requested){if(!/^\d+$/.test(requested))throw new Error('Compañía del enlace inválida.');switchCompany(Number(requested),rows);}
  }catch(e){if(active)setError((e as Error).message);}})();return()=>{active=false;};
 },[context]);
 return <section className="tracker-company" aria-label="Compañía de Tracker"><label>Compañía activa<select aria-label="Compañía activa de Tracker" value={context.company_id} disabled={!companies.length} onChange={e=>switchCompany(Number(e.target.value),companies)}>{!companies.some(c=>c.id===context.company_id)&&<option value={context.company_id}>{context.company}</option>}{companies.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label><small>La flota y los registros corresponden a esta compañía.</small>{error&&<p role="alert">{error}</p>}</section>;
}
