"use client";

import Link from "next/link";

import { categoryLabel } from "@/lib/public-data/copy";
import { setPendingQuery } from "@/lib/public-data/search-handoff";

const categories = [
  "phone",
  "wechat",
  "investment",
  "pension",
  "health_products",
  "family_impersonation",
  "customer_service",
  "collectibles",
];

export function CategorySearchLinks() {
  return (
    <div className="category-grid">
      {categories.map((category, index) => {
        const label = categoryLabel(category);
        return (
          <Link
            href="/search/"
            key={category}
            onClick={() => setPendingQuery(label)}
          >
            <span className="category-number">
              {String(index + 1).padStart(2, "0")}
            </span>
            <strong>{label}</strong>
            <span aria-hidden="true">↗</span>
          </Link>
        );
      })}
    </div>
  );
}
