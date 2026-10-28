# ADR 0001: Local-first desktop architecture with evidence-gated learning

- **Status:** Accepted (documenting the current implementation)
- **Context:** University oral-exam practice involves personal course files, hardware-constrained LLM inference, and durable feedback. The app should run without an account or hosted AI service.

## Decision

1. Use React/TypeScript for the UI, FastAPI/Python for exam and AI logic, and Tauri/Rust to manage a packaged local Python sidecar.
2. Persist user state in SQLite and exam-scoped local files/FAISS indexes; keep learning material and inference local.
3. Treat extracted documents and model outputs as untrusted inputs. Retain source provenance and require current, accepted evidence before allowing generated questions into the active study flow.
4. Combine deterministic validation, local-model checks, and regression tests, including separate synthetic real-model acceptance.
5. Use a loopback-only API with desktop launch-token and browser-origin controls; do not expose a hosted service surface.

## Alternatives considered

- **Hosted LLM backend:** simpler client packaging and potentially stronger model quality, but introduces external data transfer, recurring costs, and a network dependency.
- **Browser-only inference and persistence:** reduces native packaging complexity, but complicates compatibility with the Python PDF/vector stack and desktop lifecycle.
- **Store every generated question without validation:** faster generation, but loses the source-grounding guarantee and obscures unreliable outputs.
- **Rebuild the domain layer during desktop migration:** cleaner imports in principle, but adds regression and data-migration risk without improving the learner journey.

## Consequences

**Benefits:** local privacy, explicit data ownership, reproducible domain tests, and visible failure when sources do not support a question.

**Costs:** platform-specific native builds; local hardware/model variability; the risk that restrictive evidence gates reject useful candidates; existing Python compatibility boundaries and large modules.

## Verification and reconsideration

See [architecture](../ARCHITECTURE.md), [engineering standards](../ENGINEERING_STANDARDS.md), [privacy](../PRIVACY.md), and [desktop release checks](../desktop.md). Revisit this decision if product requirements introduce collaboration, server synchronization, cloud inference or a materially different trust model. Any such change requires a new ADR and privacy/security review.
