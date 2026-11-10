import { BackendPreview } from "./preview";
import { headers } from "next/headers";

export default async function IntegrationPreviewPage() {
  const h = await headers();
  const host = h.get("host")?.split(":")[0]?.toLowerCase();
  if (h.get("x-forwarded-host") || !["localhost","127.0.0.1","[::1]"].includes(host ?? ""))
    return <main style={{padding:32}}><h1>Local preview only</h1></main>;
  if (process.env.RELIEFMESH_ENABLE_READ_PREVIEW !== "true") {
    return <main style={{ padding: 32 }}><h1>Integration preview disabled</h1><p>The existing ReliefMesh demonstration is unchanged.</p></main>;
  }
  return <BackendPreview />;
}
