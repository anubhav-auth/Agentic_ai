# Closed Source vs. Open Source vs. Open Weight Models

*Task: difference between Closed Source, Open Source, and Open Weight models.*

The three terms are often used loosely, but they differ on **what is actually released** to the public — weights, code, and/or training data — and under what license.

---

## 1. Closed Source (Proprietary)

**What's released:** Nothing. Only API/product access — no weights, no training code, no training data.

**Examples:** GPT-4/5 (OpenAI), Claude (Anthropic), Gemini (Google).

**Characteristics:**
- Runs only on the vendor's infrastructure; you cannot download or self-host it.
- "Fine-tuning" (if offered) happens through the vendor's managed API, not by touching raw weights yourself.
- Vendor controls versioning, deprecation, pricing, and usage policy.
- Usually the most capable frontier models, backed by the vendor's full training pipeline and safety tuning.

---

## 2. Open Source (in the strict sense)

**What's released:** Weights **and** training code **and** (ideally) training data / data pipeline, under an OSI-recognized open license (e.g., Apache 2.0, MIT).

**Examples:** OLMo (Allen Institute for AI), Pythia (EleutherAI) — models built specifically to be fully reproducible end-to-end.

**Characteristics:**
- You can inspect, modify, retrain from scratch, and redistribute freely, including commercially, without usage-based restrictions.
- Genuinely rare among high-capability models — full training-data disclosure is uncommon because of licensing, privacy, and competitive concerns.
- Best choice when reproducibility, auditability, or research transparency is a hard requirement.

---

## 3. Open Weight

**What's released:** Just the trained weights (downloadable), usually with inference/fine-tuning code — but **not** the full training data or complete training methodology.

**Examples:** Llama family (Meta), Mistral models, Gemma (Google), Qwen (Alibaba), DeepSeek.

**Characteristics:**
- You can download, run locally, quantize, and fine-tune the model.
- License is often *not* a strict open-source license — many include usage conditions (e.g., Llama's license restricts certain very-large-scale commercial deployments, requires attribution).
- You cannot fully reproduce the model from scratch, since the original training data/pipeline isn't public.
- This is the category most "open" LLMs on Hugging Face actually fall into — the label "open source" is frequently misapplied to what is really open weight.

---

## 4. Comparison Table

| Dimension | Closed Source | Open Source | Open Weight |
|---|---|---|---|
| Weights downloadable | No | Yes | Yes |
| Training code released | No | Yes | Sometimes (inference/fine-tune code, not full pretraining) |
| Training data released | No | Ideally yes | No |
| Self-hosting possible | No | Yes | Yes |
| Full reproducibility from scratch | No | Yes | No |
| License restrictions on commercial use | Vendor terms of service | Usually none (permissive) | Often yes (usage caps, attribution, field-of-use limits) |
| Typical capability tier | Frontier / highest | Varies, often smaller/research-focused | Wide range, competitive with closed models at similar scale |

## 5. Practical Note

When a client says they want an "open source model," clarify whether they actually need:
- **True open source** (rare, needed for regulatory/auditability requirements around training data provenance), or
- **Open weight** (the common case — self-hosting, fine-tuning, data-residency control — which covers the vast majority of real "run it ourselves" use cases).

Most on-prem/private-deployment client requirements are satisfied by open-weight models; true open source is only necessary when the training data itself must be auditable.
