import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "CritMatch",
  description: "EHR-embedded cohort identification application",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
