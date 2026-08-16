import Link from "next/link";

export function SiteHeader() {
  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link className="brand" href="/" aria-label="骗局雷达首页">
          <span className="radar-mark" aria-hidden="true">
            <span />
          </span>
          <span className="brand-copy">
            <strong>骗局雷达</strong>
            <small>SCAM RADAR</small>
          </span>
        </Link>
        <nav className="primary-nav" aria-label="主要导航">
          <Link href="/search/">查一查</Link>
          <Link href="/#methodology">我们怎么判断</Link>
        </nav>
      </div>
    </header>
  );
}
