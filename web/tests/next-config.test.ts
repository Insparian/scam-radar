import { describe, expect, it } from "vitest";

import nextConfig from "../next.config";

describe("local demo configuration", () => {
  it("loads client scripts when the demo is opened through 127.0.0.1", () => {
    expect(nextConfig.allowedDevOrigins).toContain("127.0.0.1");
  });
});
