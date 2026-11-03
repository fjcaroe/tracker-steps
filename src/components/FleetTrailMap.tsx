import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {GoogleMap,MarkerF,PolylineF,useJsApiLoader} from '@react-google-maps/api';
import {MAPS_LIBRARIES,MAPS_LOADER_ID} from '../mapsConfig';
import {meters,routeAnchors,type TrailPoint,type Stop,type TrailGap} from '../services/fleetTrail';
type XY={lat:number;lng:number};
type RouteAPI={Route:{computeRoutes:(r:{origin:XY;destination:XY;intermediates:{location:XY}[];travelMode:string;fields:string[]})=>Promise<{routes?:{path?:XY[]}[]}>}};
const xy=(p:{lat:number;lon:number}):XY=>({lat:p.lat,lng:p.lon});
const center={lat:-33.45,lng:-70.65};
export default function FleetTrailMap({points,segments,stops,gaps=[],cursor,follow=false,onlyParking=false}:{points:TrailPoint[];segments:TrailPoint[][];stops:Stop[];gaps?:TrailGap[];cursor:TrailPoint|undefined;follow?:boolean;onlyParking?:boolean}){
 const {isLoaded,loadError}=useJsApiLoader({id:MAPS_LOADER_ID,libraries:MAPS_LIBRARIES,googleMapsApiKey:import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string});
 const [map,setMap]=useState<google.maps.Map|null>(null),[satellite,setSatellite]=useState(false),[estimate,setEstimate]=useState<XY[][]>([]),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const generation=useRef(0);
 const routes=useMemo(()=>segments.filter(s=>s.length>1),[segments]);
 const fit=useCallback(()=>{if(!map||!points.length)return;const bounds=new google.maps.LatLngBounds();const visible=onlyParking?[points[0]]:[...segments.flat(),...stops.map(s=>s.point),...gaps.flatMap(g=>[g.before,g.after])];visible.forEach(p=>bounds.extend(xy(p)));if(!visible.length)return;map.fitBounds(bounds,55);if(visible.length===1)map.setZoom(16);},[map,points,segments,stops,gaps,onlyParking]);
 useEffect(()=>{fit();},[fit]);
 useEffect(()=>{setEstimate([]);setError('');setBusy(false);},[points]);
 useEffect(()=>{if(follow&&cursor&&map)map.panTo(xy(cursor));},[follow,cursor,map]);
 // Discard responses from a previous period/segment, even if the provider cannot abort.
 useEffect(()=>{return()=>{generation.current++;};},[points]);
 const approximate=async()=>{
  if(!routes.length)return;
  const token=++generation.current;setBusy(true);setError('');setEstimate([]);
  try{
   const {Route}=await google.maps.importLibrary('routes') as unknown as RouteAPI;
   const paths:XY[][]=[];
   for(const original of routes){
    if(token!==generation.current)return;
    const anchors=routeAnchors(original);if(anchors.length<2)continue;
    const result=await Route.computeRoutes({origin:xy(anchors[0]),destination:xy(anchors[anchors.length-1]),intermediates:anchors.slice(1,-1).map(p=>({location:xy(p)})),travelMode:'DRIVING',fields:['path']});
    if(token!==generation.current)return;
    const path=result.routes?.[0]?.path;
    if(!path||path.length<2)throw new Error('No se encontró una aproximación por calles para el recorrido.');
    let raw=0,road=0;for(let i=1;i<original.length;i++)raw+=meters(original[i-1],original[i]);for(let i=1;i<path.length;i++)road+=meters({lat:path[i-1].lat,lon:path[i-1].lng},{lat:path[i].lat,lon:path[i].lng});
    if(road>raw*3+500)throw new Error('La ruta sugerida se aleja demasiado de la traza. Se conserva el recorrido GPS.');
    paths.push(path);
   }
   setEstimate(paths);
  }catch(e){if(token===generation.current)setError((e as Error).message.includes('traza')||(e as Error).message.includes('aproximación')?(e as Error).message:'No fue posible consultar la aproximación de Google. La traza GPS sigue disponible.');}
  finally{if(token===generation.current)setBusy(false);}
 };
 return <div className="trail-map-panel"><div className="trail-map-tools"><button onClick={fit} disabled={!map}>Centrar recorrido</button><button onClick={()=>setSatellite(v=>!v)} aria-pressed={satellite}>{satellite?'Ver calles':'Satélite'}</button><button disabled={!isLoaded||busy||!routes.length||routes.length>12} onClick={()=>void approximate()}>{busy?'Calculando…':'Aproximar por calles'}</button>{estimate.length>0&&<button onClick={()=>setEstimate([])}>Quitar aproximación</button>}</div>
 {routes.length>12&&<p className="trail-map-notice">Reduce el período para aproximar por calles. El recorrido GPS completo sigue visible.</p>}
 {error&&<p className="trail-map-notice" role="alert">{error}</p>}
 <div className="trail-map-canvas">{loadError?<p role="alert">Google Maps no pudo cargar. Revisa tu conexión.</p>:!isLoaded?<p role="status">Cargando mapa del recorrido…</p>:<GoogleMap mapContainerStyle={{height:'100%',width:'100%'}} center={center} zoom={12} onLoad={setMap} options={{mapTypeId:satellite?'hybrid':'roadmap',mapTypeControl:false,streetViewControl:false,fullscreenControl:true,gestureHandling:'cooperative',clickableIcons:false,maxZoom:18}}>
 {segments.filter(s=>s.length>1).map((s,i)=><PolylineF key={i} path={s.map(xy)} options={{strokeColor:'#17634c',strokeWeight:5,strokeOpacity:.85}}/>)}
 {estimate.map((path,i)=><PolylineF key={i} path={path} options={{strokeColor:'#2563eb',strokeWeight:5,strokeOpacity:0,icons:[{icon:{path:'M 0,-1 0,1',strokeOpacity:1,scale:3},offset:'0',repeat:'15px'}]}}/>)}
 {onlyParking&&points[0]&&<MarkerF position={xy(points[0])} label="P" title="Reposo probable"/>}
 {!onlyParking&&points[0]&&<MarkerF position={xy(points[0])} label="A" title="Inicio de los datos del período"/>}{!onlyParking&&points.length>1&&<MarkerF position={xy(points[points.length-1])} label="B" title="Fin de los datos del período"/>}
 {!onlyParking&&stops.map((s,i)=><MarkerF key={i} position={xy(s.point)} label="P" title={'Parada probable · '+Math.round(s.minutes)+' min'}/>)}
 {gaps.slice(0,20).flatMap((g,i)=>[<MarkerF key={'gap-before-'+i} position={xy(g.before)} label="!" title="Última posición antes del corte" icon={{path:google.maps.SymbolPath.CIRCLE,fillColor:'#f5d8a1',fillOpacity:1,strokeColor:'#956322',strokeWeight:2,scale:12}}/>,<MarkerF key={'gap-after-'+i} position={xy(g.after)} title="Primera posición después del corte" icon={{path:google.maps.SymbolPath.CIRCLE,fillColor:'#fff4df',fillOpacity:1,strokeColor:'#956322',strokeWeight:2,scale:7}}/>])}
 {cursor&&<MarkerF position={xy(cursor)} title="Posición en la reproducción" icon={{path:google.maps.SymbolPath.CIRCLE,fillColor:'#d8ff62',fillOpacity:1,strokeColor:'#123c33',strokeWeight:3,scale:9}}/>}
 </GoogleMap>}</div><p className="trail-map-legend">{onlyParking?<span>P · Reposo probable según posiciones registradas</span>:<><span>● Traza GPS · unión de muestras filtradas</span><span> A Inicio · B Fin · P Parada probable</span></>}{estimate.length>0&&<strong>Azul: estimación por calles, no recorrido comprobado.</strong>}</p></div>;
}
