"use client";
import { useEffect, useRef, useState } from "react";
import L from "leaflet";
import { LocateFixed, Layers } from "lucide-react";
import { useResponse } from "@/state/response-context";
import { useI18n } from "@/lib/i18n/provider";
const resourcePaths = {
  ambulance: '<path d="M3 6h11v12H3zM14 10h4l3 4v4h-7M6 10h5M8.5 7.5v5"/><circle cx="6" cy="18" r="2"/><circle cx="18" cy="18" r="2"/>',
  rescue: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><path d="m5.6 5.6 3.6 3.6m5.6 5.6 3.6 3.6m0-12.8-3.6 3.6m-5.6 5.6-3.6 3.6"/>',
  hospital: '<path d="M5 21V3h14v18M2 21h20M9 7h6M12 4v6M9 21v-6h6v6"/>',
  shelter: '<path d="m3 11 9-8 9 8M5 10v11h14V10M9 21v-7h6v7"/>',
};
function resourceSvg(type: keyof typeof resourcePaths) { return `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${resourcePaths[type]}</svg>`; }
export default function LeafletMap() {
  const ref = useRef<HTMLDivElement>(null); const map = useRef<L.Map | null>(null); const layer = useRef<L.LayerGroup | null>(null);
  const markers = useRef(new Map<string,L.Marker>()); const lastSelected = useRef<string | null>(null); const previouslyBlocked = useRef(false);
  const { data, selectedId, select } = useResponse(); const { t, language } = useI18n();
  const [ready, setReady] = useState(false); const [failedTiles, setFailedTiles] = useState(false); const [showResources, setShowResources] = useState(true);
  useEffect(() => {
    if (!ref.current || map.current) return;
    const instance = L.map(ref.current, { center: [12.93, 77.637], zoom: 13, zoomControl: false, attributionControl: true, scrollWheelZoom: false });
    map.current = instance; layer.current = L.layerGroup().addTo(instance);
    const tiles = L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>', maxZoom: 19 }).addTo(instance);
    tiles.on("tileerror", () => setFailedTiles(true)); tiles.on("tileload", () => setFailedTiles(false));
    L.control.scale({ imperial: false, position: "bottomleft" }).addTo(instance);
    const observer = new ResizeObserver(() => instance.invalidateSize()); observer.observe(ref.current);
    setReady(true);
    return () => { observer.disconnect(); tiles.off(); instance.remove(); map.current = null; layer.current = null; markers.current.clear(); lastSelected.current = null; previouslyBlocked.current = false; };
  }, []);
  useEffect(() => {
    if (!ready || !map.current) return;
    // Leaflet's built-in English zoom titles are replaced with localized numeric controls below.
    map.current.getContainer().setAttribute("aria-label", t("map.title"));
  }, [ready, t]);
  useEffect(() => {
    if (!layer.current || !data || !ready) return;
    const group = layer.current; group.clearLayers(); const live = new Set<string>();
    const upsert = (key: string, point: L.LatLngTuple, classes: string, html: string, size: L.PointTuple, title: string) => {
      live.add(key); let marker = markers.current.get(key);
      if (!marker) { marker = L.marker(point, { title, alt: title, icon: L.divIcon({ className: classes, html, iconSize: size, iconAnchor: [size[0]/2,size[1]/2] }) }).addTo(map.current!); markers.current.set(key,marker); if (key.startsWith("INC")) { marker.on("click",() => select(key)); marker.getElement()?.addEventListener("keydown",event => { if (event.key === " ") { event.preventDefault(); marker!.fire("click"); marker!.openPopup(); } }); } }
      marker.setLatLng(point); const element = marker.getElement(); if (element) { element.className = `leaflet-marker-icon ${classes} leaflet-zoom-animated leaflet-interactive`; element.innerHTML = html; element.title = title; element.setAttribute("aria-label",title); if (key.startsWith("INC")) element.setAttribute("aria-pressed",String(key === selectedId)); }
      return marker;
    };
    data.incidents.forEach(i => {
      const level = ["resolved","rejected"].includes(i.status) ? "resolved" : i.severity >= 5 ? "critical" : i.severity >= 4 ? "high" : "moderate";
      const title = `${i.id} · ${i.location} · ${t("incident.priority")} ${i.priority}`;
      const marker = upsert(i.id,[i.latitude,i.longitude],`incident-marker marker-${level} ${selectedId === i.id && !["resolved","rejected"].includes(i.status) ? "marker-selected" : "marker-muted"} ${selectedId === i.id && !["resolved","rejected"].includes(i.status) && lastSelected.current !== selectedId ? "marker-pulse" : ""}`,`<span>${i.status === "resolved" ? "✓" : i.status === "rejected" ? "×" : i.severity}</span>`,[29,29],title); marker.setZIndexOffset(selectedId === i.id ? 1000 : 100);
      const content = document.createElement("div"); content.className = "map-popup";
      const strong = document.createElement("strong"); strong.textContent = i.id; strong.dir = "ltr";
      const name = document.createElement("p"); name.textContent = i.location;
      const status = document.createElement("p"); status.textContent = `${t(`type.${i.type}`)} · ${t(`status.${i.status}`)}`;
      const priority = document.createElement("p"); priority.textContent = `${t("incident.priority")}: ${i.priority} · ${t("incident.people")}: ${i.people}`;
      content.append(strong,name,status,priority); if (marker.getPopup()) marker.setPopupContent(content); else marker.bindPopup(content, { closeButton: false });
    });
    if (showResources) data.resources.forEach(r => {
      const title = `${r.id} · ${t(`resources.${r.type}`)} · ${t(`status.${r.status}`)}`;
      const marker = upsert(r.id,[r.latitude,r.longitude],`resource-marker resource-${r.type} resource-state-${r.status} ${r.status === "unavailable" ? "marker-unavailable" : ""}`,resourceSvg(r.type),[27,27],title);
      const content = document.createElement("div"); content.className = "map-popup";
      const titleEl = document.createElement("strong"); titleEl.textContent = r.id; titleEl.dir = "ltr";
      const text = document.createElement("p"); text.textContent = `${t(`resources.${r.type}`)} · ${t(`status.${r.status}`)}`;
      const fact = document.createElement("p"); fact.textContent = `${t("resources.capacity")}: ${r.capacity}${r.eta ? ` · ${t("resources.eta")}: ${r.eta} ${t("resources.minutes")}` : ""}`;
      content.append(titleEl,text,fact); if (marker.getPopup()) marker.setPopupContent(content); else marker.bindPopup(content, { closeButton: false });
    });
    const incident = data.incidents.find(i => i.id === "INC-1042");
    if (incident && ["dispatched","blocked","replanning","awaiting_replacement"].includes(incident.status)) {
      data.resources.filter(r => r.assignedIncident === incident.id).forEach(r => L.polyline([[r.latitude,r.longitude],[incident.latitude,incident.longitude]], { color: r.id === "AMB-02" && r.eta === 24 ? "#cc4b26" : "#287466", weight: 2, dashArray: "6 7", opacity: .75 }).addTo(group));
    }
    if (incident && ["blocked","replanning","awaiting_replacement"].includes(incident.status)) L.marker([12.943,77.62], { zIndexOffset: 1200, title: t("status.blocked"), icon: L.divIcon({ className: `block-marker ${previouslyBlocked.current ? "" : "block-new"}`, html: "!", iconSize: [25,25] }) }).addTo(group);
    previouslyBlocked.current = Boolean(incident && ["blocked","replanning","awaiting_replacement"].includes(incident.status));
    markers.current.forEach((marker,key) => { if (!live.has(key)) { marker.remove(); markers.current.delete(key); } }); lastSelected.current = selectedId;
  }, [data, selectedId, select, t, language, showResources, ready]);
  const selected = data?.incidents.find(i => i.id === selectedId);
  const latitude = selected?.latitude; const longitude = selected?.longitude;
  useEffect(() => { if (map.current && latitude !== undefined && longitude !== undefined) map.current.panTo([latitude,longitude], { duration: .35, animate: !window.matchMedia("(prefers-reduced-motion: reduce)").matches }); }, [selectedId, latitude, longitude, ready]);
  const recenter = () => { if (map.current && data?.incidents.length) map.current.fitBounds(L.latLngBounds(data.incidents.map(i => [i.latitude,i.longitude])), { padding: [35,35], animate: false }); };
  return <div className="map-body"><div ref={ref} className="leaflet-canvas" />
    <div className="map-tools"><button onClick={recenter} title={t("map.center")} aria-label={t("map.center")}><LocateFixed size={18} /></button><button onClick={() => map.current?.zoomIn()} aria-label={t("map.zoomIn")}>+</button><button onClick={() => map.current?.zoomOut()} aria-label={t("map.zoomOut")}>−</button><button onClick={() => setShowResources(!showResources)} className={showResources ? "tool-active" : ""} aria-pressed={showResources} title={t("map.resourceLayers")} aria-label={t("map.resourceLayers")}><Layers size={17} /></button></div>
    {data?.incidents.some(i => i.id === "INC-1042" && ["blocked","replanning","awaiting_replacement"].includes(i.status)) && <div className="map-warning" role="status">{t("route.disruption")} · <b dir="ltr">AMB-02</b></div>}
    {failedTiles && <div className="tile-warning" role="status">{t("map.tiles")}</div>}
    <div className="assignment-caption">{t("map.assignmentLines")}</div>
    <div className="map-legend" aria-label={t("map.legend")}>{["critical","high","moderate"].map(level => <span key={level}><i className={`legend-${level}`} />{t(`severity.${level}`)}</span>)}{["ambulance","rescue","hospital","shelter"].map(type => <span key={type}><i className={`legend-${type}`} />{t(`resources.${type}`)}</span>)}</div>
  </div>;
}
