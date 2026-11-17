# Manual checks (synthetic examples, not a golden set)

These files were written for local inspection. They do not establish any SRS accuracy targets.

- `sk.txt`: language sk; region Košický kraj; Backend; annual EUR 42,000–48,000 gross, monthly equivalent 3,500–4,000; Python, Django, Docker, Kubernetes and English required; CKA optional; Rust must not be accepted.
- `en.txt`: language en; ML; EUR 2,000–2,600 gross/month; Python, SQL and Pandas required; AWS certification optional; Java benefits must not become a requirement.
- `cs.txt`: language cs; CZK 60,000–80,000 gross/month; Prague must not become a Slovak region; Python and PostgreSQL required; Docker optional. Czech language recognition from inflected `češtinu` may need an explicit alias: inspect uncertain items rather than inventing evidence.
- `adversarial.txt`: MUST go to review due to embedded instructions. Accepted skill lists must not contain Java, Rust, Kubernetes, or an invented AWS certification.

Evidence contract: for every accepted mention, `source_text[start:end] == quote`; the quote contains the original surface spelling. Rejected/uncertain mentions must not appear in `required_skills`, `technologies` or `certificates`. `field_evidence` contains literal quotes supporting validated metadata.
