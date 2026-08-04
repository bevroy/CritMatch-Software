import type { Metadata } from "next";
import "./globals.css";
import SiteHeader from "./SiteHeader";

export const metadata: Metadata = {
  title: "CritMatch | Clinical Research Platform",
  description: "CritMatch is a platform for equitable clinical research participation.",
  icons: {
    icon: "/critmatch-logo.png",
    apple: "/critmatch-logo.png",
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
