"use client";
import { useEffect, useRef, useState } from "react";
import { decideRevision } from "../../lib/services/revision-guard";
import { refreshFailed, refreshSucceeded } from "../../lib/services/refresh-state";
import { classifyPreviewStatus, previewStatusMessage } from "../../lib/services/preview-connection-status";
import { validPreviewProjection } from "../../lib/services/preview-projection";
import { validPreviewReferences } from "../../lib/services/preview-references";
type Incident = { id:string; location:string; type:string; severity:string; status:string; operational_phase:string; priority_score:number|null; people_affected:number|null };
type Resource = { id:string; location:string; type:string; status:string; capacity:number|null };
type Assignment = {id:string;incident_id:string;resource_id:string;status:string;assigned_at:string};
type Recommendation = {incident:string;version:number;state:string;recommended_resources:string[]};
type Preview = { mode:"read_only_preview"; generated_at:string; revision:number; incidents:Incident[]; resources:Resource[]; assignments:Assignment[]; recommendations:Recommendation[] };
function isPreview(v: unknown): v is Preview {
  return validPreviewProjection(v) && validPreviewReferences(v);
}
export function BackendPreview() {
  const [data,setData] = useState<Preview|null>(null);
  const latestRevision = useRef<number|null>(null);
  const [error,setError] = useState<string|null>(null);
  const [stale,setStale] = useState(false);
  const [loading,setLoading] = useState(true);
  const [refresh,setRefresh] = useState(0);
  useEffect(()=>{
    const controller = new AbortController();
    fetch("/api/backend-preview", {cache:"no-store",signal:controller.signal})
      .then(async r=>{if(!r.ok) {
        const body: unknown = await r.json().catch(()=>null);
        const code = body && typeof body === "object" && "error" in body && typeof body.error === "string" ? body.error : null;
        throw new Error(previewStatusMessage(classifyPreviewStatus(r.status,code)));
      } return r.json() as Promise<unknown>;})
      .then(v=>{if(!isPreview(v)) throw new Error("Unexpected preview response");
        const decision = decideRevision(latestRevision.current,v.revision);
        if (decision !== "accept") throw new Error(decision === "stale" ? "Stale backend snapshot rejected" : "Invalid backend revision");
        latestRevision.current = v.revision;
        setData(v);setError(null);setStale(refreshSucceeded().state === "stale");})
      .catch(e=>{if(!controller.signal.aborted){setError(e instanceof Error?e.message:"Preview failed");setStale(refreshFailed(latestRevision.current !== null).state === "stale");}})
      .finally(()=>{if(!controller.signal.aborted)setLoading(false);});
    return ()=>controller.abort();
  },[refresh]);
  return <main style={{maxWidth:1100,margin:"0 auto",padding:24}}>
    <h1>ReliefMesh — backend integration preview</h1>
    <p><strong>READ ONLY.</strong> This page displays backend data separately from the simulated command center. It cannot approve, dispatch, modify or resolve incidents.</p>
    <p><a href="/">Return to simulated demo</a></p>
    <button type="button" onClick={()=>{setLoading(true);setRefresh(n=>n+1);}}>Refresh backend data</button>
    {loading && <p role="status">Loading backend data…</p>}
    {error && <p role="alert">{error}. {data ? "Previously loaded data is retained for reference only and must not be treated as current." : "No backend data is available."} No simulated data has been substituted.</p>}
    {data && !loading && <>
      {stale && <p role="alert"><strong>STALE / UNVERIFIED DATA — NOT CURRENT.</strong> Do not use these records for operational decisions.</p>}
      <p role="status">{data.incidents.length} incidents and {data.resources.length} resources returned from one coherent development snapshot. No live synchronization is enabled.</p>
      <p>Snapshot generated: {data.generated_at}. Operational revision: {data.revision}.</p>
      <h2>Incidents</h2>
      <div style={{overflowX:"auto"}}><table><thead><tr><th scope="col">ID</th><th scope="col">Location</th><th scope="col">Type</th><th scope="col">Severity</th><th scope="col">Phase</th><th scope="col">Priority</th></tr></thead><tbody>
      {data.incidents.map(i=><tr key={i.id}><td>{i.id}</td><td>{i.location}</td><td>{i.type}</td><td>{i.severity}</td><td>{i.operational_phase}</td><td>{i.priority_score??"Unknown"}</td></tr>)}
      </tbody></table></div>
      <h2>Recommendations</h2>
      <div style={{overflowX:"auto"}}><table><thead><tr><th scope="col">Incident</th><th scope="col">Version</th><th scope="col">State</th><th scope="col">Proposed resources</th></tr></thead><tbody>
      {data.recommendations.map(r=><tr key={`${r.incident}:${r.version}`}><td>{r.incident}</td><td>{r.version}</td><td>{r.state}</td><td>{r.recommended_resources.join(", ")}</td></tr>)}
      </tbody></table></div>
      <h2>Assignment history</h2>
      <div style={{overflowX:"auto"}}><table><thead><tr><th scope="col">Assignment</th><th scope="col">Incident</th><th scope="col">Resource</th><th scope="col">Status</th><th scope="col">Assigned at</th></tr></thead><tbody>
      {data.assignments.map(a=><tr key={a.id}><td>{a.id}</td><td>{a.incident_id}</td><td>{a.resource_id}</td><td>{a.status}</td><td>{a.assigned_at}</td></tr>)}
      </tbody></table></div>
      <h2>Resources</h2>
      <div style={{overflowX:"auto"}}><table><thead><tr><th scope="col">ID</th><th scope="col">Location</th><th scope="col">Type</th><th scope="col">Status</th><th scope="col">Capacity</th></tr></thead><tbody>
      {data.resources.map(r=><tr key={r.id}><td>{r.id}</td><td>{r.location}</td><td>{r.type}</td><td>{r.status}</td><td>{r.capacity??"Unknown"}</td></tr>)}
      </tbody></table></div>
    </>}
  </main>;
}
