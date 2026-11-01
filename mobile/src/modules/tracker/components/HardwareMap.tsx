import {useCallback,useEffect,useState} from 'react';
import {GoogleMap,OverlayViewF,OverlayView,useJsApiLoader} from '@react-google-maps/api';
import type {MapMarker} from './MapView';
import type {LatLon} from '../lib/nav';

const INITIAL_CENTER={lat:-33.45,lng:-70.65};

export default function HardwareMap({markers,focus}:{markers:MapMarker[];focus:LatLon|null}){
 const key=import.meta.env.VITE_GOOGLE_MAPS_API_KEY||'';
 const {isLoaded,loadError}=useJsApiLoader({id:'steps-hardware-google',googleMapsApiKey:key,language:'es',region:'CL'});
 const [map,setMap]=useState<google.maps.Map|null>(null);
 const [satellite,setSatellite]=useState(false),[traffic,setTraffic]=useState(false);
 const fit=useCallback(()=>{if(!map||!markers.length)return;const bounds=new google.maps.LatLngBounds();markers.forEach(p=>bounds.extend({lat:p.lat,lng:p.lon}));map.fitBounds(bounds,70);},[map,markers]);
 useEffect(()=>{if(map&&markers.length)fit();},[map,markers.length]);
 useEffect(()=>{if(map&&focus){map.panTo({lat:focus.lat,lng:focus.lon});map.setZoom(17);}},[map,focus]);
 useEffect(()=>{if(!map||!traffic)return;const layer=new google.maps.TrafficLayer();layer.setMap(map);return()=>layer.setMap(null);},[map,traffic]);
 return <section className="hardware-map" aria-label="Mapa de vehículos"><div className="hardware-map-tools"><button onClick={()=>setSatellite(v=>!v)} aria-pressed={satellite}>{satellite?'Ver calles':'Satélite'}</button><button onClick={()=>setTraffic(v=>!v)} aria-pressed={traffic}>Tráfico</button><button onClick={fit} disabled={!map||!markers.length}>Ver toda la flota</button></div>
 {!key||loadError?<div className="hardware-map-error" role="alert"><strong>Google Maps no está disponible</strong><p>Revisa la conexión y la autorización del mapa. Las posiciones siguen disponibles en las fichas de vehículos.</p></div>:!isLoaded?<p role="status">Cargando Google Maps…</p>:<GoogleMap mapContainerClassName="hardware-google-canvas" center={INITIAL_CENTER} zoom={12} onLoad={setMap} onUnmount={()=>setMap(null)} mapTypeId={satellite?'hybrid':'roadmap'} options={{mapTypeControl:false,streetViewControl:true,fullscreenControl:true,gestureHandling:'cooperative',clickableIcons:false,minZoom:3,maxZoom:19,styles:[{featureType:'poi',stylers:[{visibility:'off'}]},{featureType:'transit',stylers:[{visibility:'off'}]}]}}>
 {markers.map((p,i)=><OverlayViewF key={i} position={{lat:p.lat,lng:p.lon}} mapPaneName={OverlayView.OVERLAY_MOUSE_TARGET}><div className={'hardware-car-pin mk--'+p.kind} title={p.label} aria-label={p.label}><svg viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="m5 10 2-5h10l2 5M5 10h14v8H5zM7 18v2m10-2v2M7 13h2m6 0h2"/></svg></div></OverlayViewF>)}
 </GoogleMap>}</section>;
}
