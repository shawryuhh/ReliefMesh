import type { Metadata } from "next";
import { I18nProvider } from "@/lib/i18n/provider";
import { ResponseProvider } from "@/state/response-context";
import "leaflet/dist/leaflet.css";
import "./globals.css";
import "./interaction.css";
import "./fonts.css";
import "./presentation.css";
export const metadata: Metadata = { title: "ReliefMesh — Command Center", description: "A frontend-only crisis coordination demonstration with simulated incidents and dispatch." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><body><I18nProvider><ResponseProvider>{children}</ResponseProvider></I18nProvider></body></html>;
}
