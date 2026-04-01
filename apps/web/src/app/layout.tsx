import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenGuesser",
  description: "Multiplayer GeoGuesser clone powered by OpenStreetMap and Mapillary",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

