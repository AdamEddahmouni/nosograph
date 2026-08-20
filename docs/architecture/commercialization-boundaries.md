# Commercialization Boundaries

**Status:** Documentation only — no billing implementation in scope.

## Open-source core (Apache-2.0)

The NosoGraph source code, CLI, web dashboard, pipeline modules, and JSON schema definitions are open source under Apache-2.0.

## What remains free and forkable

- Disease module schema and validation tooling
- Evidence Workspace (minus optional LLM API costs borne by deployer)
- Universal biomed store and import adapters
- Dashboard and `/api/v1` read endpoints
- Docker compose self-hosting

## Optional commercial layers (NOT IMPLEMENTED)

These are **architectural placeholders** for future products — not present in this repository:

| Layer | Description | Status |
|-------|-------------|--------|
| Hosted SaaS | Managed NosoGraph cloud | PLANNED |
| Enterprise SSO | SAML/OIDC integration | PLANNED |
| Premium data feeds | Licensed third-party datasets | PLANNED |
| Support contracts | SLA-backed support | PLANNED |
| Stripe billing | Subscription payments | NOT_IMPLEMENTED |

## Boundary rules for contributors

1. Do not commit API keys, license keys, or customer data.
2. Keep proprietary connectors in separate repositories if they require closed licenses.
3. Document any optional paid external API (OpenAI, etc.) as deployer responsibility.
4. Do not frame OSS features as "free trial" of unreleased commercial products.

## Trademark

"NosoGraph" is the product name. See [trademark-policy.md](../legal/trademark-policy.md). Forks must not imply official endorsement.

## Dual licensing

If enterprise features are added later, they should live in a separate repository or optional extra under a commercial license — the Apache-2.0 core must remain buildable without them.

## Research vs clinical products

NosoGraph OSS is **research-only**. Any future clinical decision support product would require separate regulatory validation and must not reuse OSS disclaimers.
