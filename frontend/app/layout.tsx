import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Ironvale · Shop-floor assistant",
  description: "Procedures, plant numbers and supplier links for Ironvale Components, with citations.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
