import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "ElicitSense",
  description:
    "Requirements elicitation meetings to an evidence-linked requirements register, with uncertainty cues, cross-meeting change tracking and cited Q&A.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body>
        <header className="site-header">
          <div className="wrap">
            <Link href="/" className="brand">
              Elicit<span>Sense</span>
            </Link>
            <nav className="nav">
              <Link href="/p/harbour_physio/">Harbour Physio</Link>
              <Link href="/p/fernhill_bakery/">Fernhill Bakery</Link>
              <Link href="/evaluation/">Evaluation</Link>
              <Link href="/method/">Method and limits</Link>
            </nav>
          </div>
        </header>
        <main>{children}</main>
        <footer className="site-footer">
          <div className="wrap">
            Demo mode: every requirement, link, answer and score on this site was produced by a real run of the
            ElicitSense pipeline on synthetic, fictional meetings. Nothing here was written by hand to look like model
            output.
          </div>
        </footer>
      </body>
    </html>
  );
}
