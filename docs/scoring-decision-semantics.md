# Scoring Decision Semantics

## Decision order
- Manual override wins immediately.
- Hard HOME blockers win immediately.
- Pure ASN, provider markers, keywords, behavioral signals, learning, and fallback checks accumulate a signed score.
- Provider guardrails may block automation, but they do not rewrite the underlying verdict.
- Final verdict and confidence are derived from the signed score.
- Punitive eligibility is computed after verdict selection and respects automation guardrails.

## Score truth table
- `score >= threshold_mobile` -> `MOBILE / HIGH_MOBILE`
- `score >= threshold_probable_mobile` -> `MOBILE / PROBABLE_MOBILE`
- `score <= -threshold_probable_home` -> `HOME / HIGH_HOME`
- `score <= -threshold_home` -> `HOME / PROBABLE_HOME`
- everything else -> `UNSURE / UNSURE`

This keeps the neutral zone neutral: weak or ambiguous evidence does not collapse into `HOME`.

## Guardrails
- `provider_evidence.review_recommended=true` blocks automation for ambiguous mixed-provider cases.
- `automation_guardrail.blocked=true` is an explicit trace that the verdict may exist, but automation must not act on it.
- Verdict and automation are intentionally separate states.
