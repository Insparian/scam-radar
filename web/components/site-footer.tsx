import Link from "next/link";

export function SiteFooter({ releaseId }: { releaseId: string }) {
  return (
    <footer className="site-footer">
      <div className="shell footer-grid">
        <div>
          <div className="footer-title">骗局雷达</div>
          <p>把可信公开信息整理成简单、可搜索、可追溯的骗局模式。</p>
        </div>
        <nav aria-label="信任与说明">
          <Link href="/#methodology">判断方法</Link>
          <Link href="/#sources">来源范围</Link>
          <Link href="/#privacy">隐私</Link>
          <Link href="/#corrections">更正与下架</Link>
          <Link href="/#about">关于我们</Link>
        </nav>
        <div className="release-note">
          <span>本页内容版本</span>
          <code>{releaseId}</code>
        </div>
      </div>
    </footer>
  );
}
