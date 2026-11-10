"use client";
import dynamic from "next/dynamic";
import { MapPinned } from "lucide-react";
import { useI18n } from "@/lib/i18n/provider";
import { useResponse } from "@/state/response-context";
import { StateMessage } from "@/components/common/ui";
function MapLoading() { return <StateMessage kind="loading" message="common.loading" />; }
const LeafletMap = dynamic(() => import("./leaflet-map"), { ssr: false, loading: MapLoading });
export function MapPanel() {
  const { t } = useI18n(); const { data, selectedId } = useResponse(); const selected = data?.incidents.find(i => i.id === selectedId);
  return <section className="panel map-panel"><div className="panel-heading"><h2><MapPinned size={17} />{t("map.title")}</h2><span className="map-sector" dir="ltr">{selected ? `${selected.latitude.toFixed(4)}°, ${selected.longitude.toFixed(4)}°` : "—"}</span></div><LeafletMap /></section>;
}
