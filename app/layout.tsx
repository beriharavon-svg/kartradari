import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KartRadarı | TCG Market Intelligence",
  description: "Kart piyasası için fiyat, hype, sealed ve portföy takip platformu.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="tr">
      <body>{children}</body>
    </html>
  );
}
