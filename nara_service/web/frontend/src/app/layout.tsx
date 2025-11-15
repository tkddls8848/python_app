import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NARA Service Dashboard",
  description: "정부 서비스 상태 대시보드",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ko">
      <body className="antialiased">
        {children}
      </body>
    </html>
  );
}
