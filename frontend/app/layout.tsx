import "@fontsource-variable/manrope";
import "@fontsource/instrument-serif/400.css";
import "@fontsource/instrument-serif/400-italic.css";
import "@fontsource/ibm-plex-mono/400.css";
import "@fontsource/ibm-plex-mono/500.css";
import "./globals.css";
import type { Metadata, Viewport } from "next";
import { themeInitScript } from "@/components/theme";
import { BRAND } from "@/lib/brand";

export const metadata: Metadata = {
  title: { default: `${BRAND.name} — ${BRAND.descriptor}`, template: `%s · ${BRAND.name}` },
  description: "n8n-orchestrated AI agents for enterprise case handling and tender responses, with a human approval in front of every consequential action.",
  applicationName: BRAND.name,
  icons: { icon: [{ url: "/icon.svg", type: "image/svg+xml" }], apple: "/apple-touch-icon.png" },
  openGraph: { title: BRAND.name, description: BRAND.descriptor, images: ["/media/og.jpg"], type: "website" },
};

export const viewport: Viewport = {
  themeColor: [{ media: "(prefers-color-scheme: light)", color: "#F4F0E8" }, { media: "(prefers-color-scheme: dark)", color: "#070A14" }],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="light" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeInitScript }} /></head>
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
