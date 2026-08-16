import Link from "next/link";

export default function NotFound() {
  return (
    <main id="main-content" className="not-found shell">
      <span className="section-kicker">404 · 没有这条记录</span>
      <h1>
        这页可能已被更正、下架，
        <br />
        或者从未公开。
      </h1>
      <p>没有找到页面不代表相关对象一定安全。你可以换一个简单关键词再查。</p>
      <div>
        <Link className="button-primary" href="/search/">
          重新查一查
        </Link>
        <Link className="text-link" href="/">
          返回首页
        </Link>
      </div>
    </main>
  );
}
