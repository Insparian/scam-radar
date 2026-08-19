import type { Metadata } from "next";

import { AdminShell } from "@/components/admin-shell";

export const metadata: Metadata = {
  title: { default: "运营台", template: "%s｜骗局雷达运营台" },
  robots: { index: false, follow: false, nocache: true },
};

export default function AdminLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AdminShell>{children}</AdminShell>;
}
