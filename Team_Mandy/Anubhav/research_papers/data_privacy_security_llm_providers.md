# Data Privacy & Security — OpenAI, Anthropic, Google

*Task 1 backlog item — comparison of data privacy/security practices across the three major LLM providers.*

> Note: Provider policies change frequently. Treat this as a working summary and verify current terms against each provider's official Trust/Privacy Center before relying on it for a client commitment.

---

## 1. OpenAI

**Training data usage**
- API usage (including via products built on the API): not used to train OpenAI's models by default.
- ChatGPT Enterprise / Team: conversations are not used for training by default.
- ChatGPT Free / Plus (consumer): conversations may be used to improve models unless the user disables "Improve the model for everyone" in Data Controls, or uses Temporary Chat (not saved, not used for training).

**Data retention**
- API: request/response data retained 30 days by default for abuse and safety monitoring, then deleted. Zero Data Retention (ZDR) is available for eligible API customers (mainly high-trust enterprise use cases).
- Enterprise/Team: admin-configurable retention windows.

**Security & compliance**
- SOC 2 Type II certified.
- GDPR: Data Processing Addendum (DPA) available; supports EU data residency for some enterprise tiers.
- Encryption in transit (TLS) and at rest.
- Enterprise controls: SSO/SAML, SCIM provisioning, audit logs, admin-managed workspace controls.

---

## 2. Anthropic (Claude)

**Training data usage**
- API usage and Claude for Work / Enterprise: not used to train models by default.
- Claude.ai consumer product: conversations may be used to improve models unless the user opts out in privacy settings; users can also delete conversation history.

**Data retention**
- Default retention policies apply to API data for trust & safety purposes, with configurable/shorter retention for enterprise agreements.
- Zero Data Retention available for qualifying API customers with an approved use case.

**Security & compliance**
- SOC 2 Type II certified.
- ISO 27001 certified.
- HIPAA: Business Associate Agreements (BAA) available for eligible customers (API/Enterprise).
- GDPR-compliant DPA available.
- Emphasizes Constitutional AI / safety-by-design approach as part of its security posture, alongside standard encryption in transit/at rest.

---

## 3. Google (Gemini / Vertex AI)

**Training data usage**
- Google Cloud / Vertex AI (enterprise): customer data submitted via the API is **not** used to train Google's foundation models without explicit customer permission — governed by Cloud data processing terms, isolated from consumer products.
- Consumer Gemini app: conversations may be reviewed by human reviewers and used to improve services unless "Gemini Apps Activity" is turned off; retained per Google account activity settings.

**Data retention**
- Vertex AI: customer-configurable retention; supports data residency controls in specific regions.
- Consumer Gemini: tied to general Google Account activity/retention controls (Gemini Apps Activity).

**Security & compliance**
- SOC 1/2/3 certified.
- ISO 27001, 27017, 27018 certified.
- HIPAA BAA available on Google Cloud (Vertex AI).
- GDPR-compliant terms; data residency options in select regions.
- Vertex AI supports VPC Service Controls and Customer-Managed Encryption Keys (CMEK) for enterprise-grade isolation.

---

## 4. Comparison Summary

| Dimension | OpenAI | Anthropic | Google |
|---|---|---|---|
| API data used for training | No (default) | No (default) | No (default, Cloud/Vertex) |
| Consumer product used for training | Opt-out available | Opt-out available | Tied to account activity settings |
| Zero Data Retention option | Yes (eligible API customers) | Yes (eligible API customers) | Configurable retention (Vertex AI) |
| SOC 2 Type II | Yes | Yes | Yes (SOC 1/2/3) |
| ISO 27001 | Not primary certification cited | Yes | Yes (27001/27017/27018) |
| HIPAA BAA available | Enterprise tiers | Eligible customers | Yes (Vertex AI) |
| GDPR DPA | Yes | Yes | Yes |
| Enterprise access controls (SSO, audit logs) | Yes | Yes | Yes |

## 5. Practical Takeaway for Clients

- For any client-facing or regulated deployment (banking, healthcare, HR), always use the **API/Enterprise tier**, not the free consumer product — all three providers separate consumer-product data handling from enterprise/API data handling.
- Request Zero Data Retention where the workflow touches sensitive data (PII, financial records, health records).
- Confirm HIPAA BAA availability explicitly if handling health data — this is tier-gated for all three providers, not automatic.
- Get the current DPA/subprocessor list from the provider before finalizing any compliance sign-off, since these documents are updated more frequently than general policy pages.
