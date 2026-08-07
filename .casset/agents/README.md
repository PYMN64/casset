# Casset Agent System v1.0

Agents are introduced only after the Project Brain and test foundation are established.

## Roles
- **Architect** — reviews requirements and proposes architecture/ADR changes. Does not silently alter architecture.
- **Product** — converts product goals into bounded feature specifications and acceptance criteria.
- **Developer** — implements an approved feature within existing domain boundaries.
- **Tester** — creates regression/unit/integration tests and validates acceptance criteria.
- **Reviewer** — reviews correctness, coupling, security, performance and Brain compliance.
- **Security** — performs focused security review for authentication, authorization, uploads, payments and abuse controls.
- **Auditor** — checks implementation against the Project Brain and reports architectural drift.

## Standard feature pipeline
Requirement → Specification → Architecture Check → Implementation → Tests → Review → Merge → Brain/Documentation update.

## Guardrails
1. Agents must read `.casset/constitution.md` before work.
2. Agents must not rewrite architecture without an explicit decision record.
3. Agents must not weaken tests to make a feature pass.
4. Agents must not treat generated code as authoritative over the Brain.
5. High-risk changes require review before merge.
