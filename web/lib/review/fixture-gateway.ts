import type { FixtureDecision, ReviewGateway } from "./types";

export class FixtureReviewGateway implements ReviewGateway {
  async decide(itemId: string, decision: FixtureDecision, note: string) {
    if (!itemId || !decision || note.length > 500)
      throw new Error("Invalid fixture review action");
    await Promise.resolve();
    return { ok: true, fixtureOnly: true } as const;
  }
}
