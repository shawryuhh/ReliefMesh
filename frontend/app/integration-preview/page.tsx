import { BackendPreview } from "./preview";
import { headers } from "next/headers";
import { previewAllowed } from "../../lib/services/preview-access";

export default async function IntegrationPreviewPage() {
  const h = await headers();
  if (!previewAllowed(process.env.NODE_ENV, process.env.RELIEFMESH_ENABLE_READ_PREVIEW,
      h.get("host"), h.get("x-forwarded-host")))
    return <main style={{padding:32}}><h1>Local development preview only</h1></main>;
  return <BackendPreview />;
}
