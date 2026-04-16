import type { ReactNode } from "react";

export const metadata = {
  title: "AI-Driven Attack Detection Dashboard",
  description: "6G Network Anomaly Detection dashboard",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}