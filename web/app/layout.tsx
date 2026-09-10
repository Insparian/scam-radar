import type { Metadata } from "next";

import { SiteHeader } from "@/components/site-header";
import { getRelease } from "@/lib/public-data/load";

import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://scamradar.insparian.com"),
  title: {
    default: "骗局雷达｜查清套路，再决定下一步",
    template: "%s｜骗局雷达",
  },
  description:
    "把可信公开信息整理成简单、可搜索、可追溯的骗局模式，帮助你和家人先停一下、再核实。",
  applicationName: "骗局雷达",
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    locale: "zh_CN",
    siteName: "骗局雷达",
    title: "骗局雷达｜查清套路，再决定下一步",
    description:
      "最近有什么骗局值得提醒爸妈？用关键词查清套路、危险信号和第一步。",
    images: [
      {
        url: "/og.png",
        width: 1734,
        height: 907,
        alt: "骗局雷达：最近有什么骗局值得提醒爸妈？",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "骗局雷达｜查清套路，再决定下一步",
    description: "可信、清楚、可追溯的骗局模式数据库。",
    images: ["/og.png"],
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const isFixturePreview = getRelease().release_id.startsWith("fixture-");

  return (
    <html lang="zh-CN">
      <body>
        <a className="skip-link" href="#main-content">
          跳到主要内容
        </a>
        {isFixturePreview && (
          <div className="fixture-preview-banner" role="note">
            公开预览 · 当前使用固定测试资料，不代表实时骗局信息
          </div>
        )}
        <SiteHeader />
        {children}
      </body>
    </html>
  );
}
