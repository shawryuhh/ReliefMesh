import { NextResponse } from "next/server";

// Opt-in, server-side read-only connectivity probe. No browser API keys.
// This does not switch the UI away from its mock service.
export const dynamic = "force-dynamic";

export async function GET() {
  const base = process.env.RELIEFMESH_BACKEND_URL;
  if (!base) {
    return NextResponse.json({ connected: false, reason: "not_configured" }, { status: 503 });
  }
  let url: URL;
  try {
    url = new URL(base);
    if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new Error("invalid");
    // Do not allow arbitrary browser-supplied targets.
    url.pathname = "/health";
    url.search = "";
    url.hash = "";
  } catch {
    return NextResponse.json({ connected: false, reason: "invalid_configuration" }, { status: 503 });
  }
  try {
    const response = await fetch(url, {
      headers: process.env.RELIEFMESH_BACKEND_READ_KEY
        ? { "X-API-Key": process.env.RELIEFMESH_BACKEND_READ_KEY }
        : {},
      cache: "no-store",
      signal: AbortSignal.timeout(4000),
    });
    // Never reflect backend bodies or credentials to the browser.
    return NextResponse.json(
      { connected: response.ok, backendStatus: response.status },
      { status: response.ok ? 200 : 502 },
    );
  } catch {
    return NextResponse.json({ connected: false, reason: "unreachable" }, { status: 502 });
  }
}
