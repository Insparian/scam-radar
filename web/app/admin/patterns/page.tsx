import Link from "next/link";

export default function PatternsAdminPage() {
  return (
    <main id="main-content" className="admin-page admin-empty-state">
      <span className="admin-eyebrow">SCOPE LIMITED TO REVIEW QUEUE</span>
      <h1>生产模式浏览尚未接入</h1>
      <p>
        当前批准的浏览器读取边界只覆盖开放审核项。这里不会用 fixture
        冒充生产数据。
      </p>
      <Link className="button-primary" href="/admin/review/">
        返回审核队列
      </Link>
    </main>
  );
}
