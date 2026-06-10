import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OpenMox",
  description: "Enterprise Multi-Agent Collaboration Platform",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN" className="h-full">
      <body className="h-full">{children}</body>
    </html>
  );
}
