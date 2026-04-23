import type { Metadata } from "next";
import Link from "next/link";
import Image from "next/image";
import "./globals.css";

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
        <header className="site-header">
          <div className="site-header-inner">
            <Link href="/" className="brand">
              <Image
                src="/critmatch-logo.png"
                alt="CritMatch logo"
                width={552}
                height={138}
                priority
                className="brand-logo"
              />
            </Link>
          </div>
        </header>
        {children}
      </body>
    </html>
  );
}
