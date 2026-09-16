"use client";

import type { Session } from "@supabase/supabase-js";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import {
  getSupabaseBrowserClient,
  getSupabasePublicConfig,
} from "@/lib/supabase/browser";

import { AdminShell } from "./admin-shell";

type AccessState =
  | { status: "loading" }
  | { status: "ready"; session: Session }
  | { status: "configuration_missing" }
  | { status: "unauthorized"; message: string };

function isPublicAdminPath(pathname: string): boolean {
  return (
    pathname === "/admin/login" ||
    pathname === "/admin/login/" ||
    pathname === "/admin/auth/callback" ||
    pathname === "/admin/auth/callback/"
  );
}

export function AdminAuthBoundary({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const publicPath = isPublicAdminPath(pathname);
  const configured = Boolean(getSupabasePublicConfig());
  const [access, setAccess] = useState<AccessState>(() =>
    configured ? { status: "loading" } : { status: "configuration_missing" },
  );

  useEffect(() => {
    if (publicPath) return;
    if (!configured) return;

    const client = getSupabaseBrowserClient();
    let active = true;

    async function authorize(session: Session | null) {
      if (!active) return;
      if (!session) {
        const next = encodeURIComponent(pathname || "/admin/");
        window.location.replace(`/admin/login/?next=${next}`);
        return;
      }

      const { error } = await client.rpc("get_reviewer_bootstrap");
      if (!active) return;
      if (error) {
        setAccess({
          status: "unauthorized",
          message:
            "无法确认审核权限。请检查网络，或确认这个账号已启用 reviewer 权限。",
        });
        return;
      }
      setAccess({ status: "ready", session });
    }

    void client.auth.getSession().then(({ data }) => authorize(data.session));
    const { data: listener } = client.auth.onAuthStateChange(
      (_event, session) => {
        window.setTimeout(() => void authorize(session), 0);
      },
    );

    return () => {
      active = false;
      listener.subscription.unsubscribe();
    };
  }, [configured, pathname, publicPath]);

  if (publicPath) return children;

  if (access.status === "configuration_missing") {
    return (
      <main id="main-content" className="admin-access-state">
        <span className="admin-eyebrow">ADMIN CONNECTION DISABLED</span>
        <h1>审核登录尚未配置</h1>
        <p>
          当前构建没有 Supabase 的公开项目配置，因此不会发送登录或审核请求。
        </p>
      </main>
    );
  }

  if (access.status === "unauthorized") {
    return (
      <main id="main-content" className="admin-access-state">
        <span className="admin-eyebrow">ACCESS DENIED</span>
        <h1>无法进入审核台</h1>
        <p>{access.message}</p>
        <button
          className="button-primary"
          onClick={async () => {
            await getSupabaseBrowserClient().auth.signOut();
            window.location.replace("/admin/login/");
          }}
        >
          退出并换一个账号
        </button>
      </main>
    );
  }

  if (access.status !== "ready") {
    return (
      <main id="main-content" className="admin-access-state" aria-busy="true">
        <span className="admin-eyebrow">VERIFYING REVIEWER ACCESS</span>
        <h1>正在确认审核权限…</h1>
      </main>
    );
  }

  return (
    <AdminShell reviewerEmail={access.session.user.email ?? "已登录 reviewer"}>
      {children}
    </AdminShell>
  );
}
