import { createClient, type SupabaseClient } from "@supabase/supabase-js";

import type { Database } from "@/lib/generated/database.types";

export interface SupabasePublicConfig {
  url: string;
  publishableKey: string;
}

let browserClient: SupabaseClient<Database> | undefined;

export function getSupabasePublicConfig(): SupabasePublicConfig | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL?.trim();
  const publishableKey =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim();

  if (!url || !publishableKey) return null;

  try {
    const parsed = new URL(url);
    if (parsed.protocol !== "https:" && parsed.hostname !== "127.0.0.1") {
      return null;
    }
  } catch {
    return null;
  }

  return { url, publishableKey };
}

export function getSupabaseBrowserClient(): SupabaseClient<Database> {
  const config = getSupabasePublicConfig();
  if (!config) throw new Error("supabase_public_config_missing");

  browserClient ??= createClient<Database>(config.url, config.publishableKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: false,
    },
  });
  return browserClient;
}
