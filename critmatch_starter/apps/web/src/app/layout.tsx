import type { Metadata } from "next";
import "./globals.css";
import SiteHeader from "./SiteHeader";

export const metadata: Metadata = {
  title: "CritMatch",
  description: "EHR-embedded cohort identification application",
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
