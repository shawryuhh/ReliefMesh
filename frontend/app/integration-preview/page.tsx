import { BackendPreview } from "./preview";

export default function IntegrationPreviewPage() {
  if (process.env.RELIEFMESH_ENABLE_READ_PREVIEW !== "true") {
    return <main style={{ padding: 32 }}><h1>Integration preview disabled</h1><p>The existing ReliefMesh demonstration is unchanged.</p></main>;
  }
  return <BackendPreview />;
}
