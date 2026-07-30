import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { headers } from "next/headers";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host =
    requestHeaders.get("x-forwarded-host") ??
    requestHeaders.get("host") ??
    "localhost:3000";
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host.startsWith("localhost") ? "http" : "https");
  const description =
    "Public aggregate telemetry for FFXI Agent Lab progression, combat, navigation, and control reliability.";
  return {
    metadataBase: new URL(`${protocol}://${host}`),
    title: "FFXI Telemetry — Autonomy, measured",
    description,
    openGraph: {
      title: "FFXI Telemetry — Autonomy, measured",
      description,
      images: [{ url: "/og-v2.png", width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title: "FFXI Telemetry — Autonomy, measured",
      description,
      images: ["/og-v2.png"],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        {children}
      </body>
    </html>
  );
}
