import type { HeatBand, PublicPattern } from "./types";

const heatLabels: Record<HeatBand, string> = {
  immediate: "值得立即关注",
  recent: "近期值得关注",
  observe: "持续观察",
  database: "数据库记录",
};

export function heatLabel(band: HeatBand, activeAttention = true): string {
  return activeAttention ? heatLabels[band] : "历史记录";
}

export function mechanismHeading(pattern: PublicPattern): string {
  return pattern.risk_type === "risk_alert"
    ? "这种高风险做法通常如何开始"
    : "骗子通常怎么开始";
}

export function formatChineseDate(value: string): string {
  const date = new Date(value.length === 10 ? `${value}T00:00:00Z` : value);
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(date);
}

export function categoryLabel(category: string): string {
  const labels: Record<string, string> = {
    phone: "电话",
    wechat: "微信",
    investment: "投资理财",
    pension: "养老",
    health_products: "保健品",
    family_impersonation: "冒充亲友",
    customer_service: "客服",
    collectibles: "收藏品",
  };
  return labels[category] ?? category;
}
