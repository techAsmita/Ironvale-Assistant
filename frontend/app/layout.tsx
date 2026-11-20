import type { Metadata, Viewport } from "next";
import Shell from "@/components/Shell";
import { SessionProvider } from "@/lib/session";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ironvale · Shop-Floor Assistant",
  description: "Procedures, plant numbers and supplier links for Ironvale Components, with the source for every answer.",
};
export const viewport: Viewport = { themeColor: "#102B55", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="" />
        {/* eslint-disable-next-line @next/next/no-page-custom-font */}
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@500&display=swap" rel="stylesheet" />
      </head>
      <body>
        <SessionProvider><Shell>{children}</Shell></SessionProvider>
      </body>
    </html>
  );
}
