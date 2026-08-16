# Build Scam Radar V0.1 offline first

- **What:** Implement the complete fixture-based V0.1 through the offline end-to-end demo, while leaving all external activation disabled.
- **Why now:** The product, architecture, evidence, safety, and release boundaries are locked in the implementation brief, and the repository contains no application code yet.
- **Problem it solves:** It turns a large stream of trusted public reporting into a small, human-reviewable, traceable set of Scam Patterns that older adults and their families can search safely.
- **Alternative considered:** Build a public-website-only prototype first. This was rejected because it would validate presentation but not the core Attention Compression, Evidence Gate, immutable review, or provenance guarantees.
- **North Star check:** The decision directly supports Scam Radar as an intelligence engine and searchable memory rather than a scam-news or AI-content site. The main tension is implementation breadth, managed by building in the milestone order and deferring visual polish and every external action until the engine works offline.

Rui explicitly approved this decision by replying `proceed` on 2026-08-16.
