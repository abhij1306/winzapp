# Risks

| Risk | Phase | Mitigation |
|---|---:|---|
| Meta webhook retries cause duplicate bookings. | Pilot MVP | Idempotency by `wa_message_id` before flow execution. |
| In-process scheduler runs twice if Railway has multiple replicas. | Pilot MVP | One web replica only; document worker migration Post-pilot. |
| Consent flow reduces booking conversion. | Pilot MVP | Keep copy short; measure opt-in rate. |
| Report delivery links expire before patient opens. | Pilot MVP | Use 24-hour signed URLs. |
| DOB data is unreliable for password-protected PDFs. | Post-pilot | Defer password protection until DOB workflow exists. |
| LLM fallback misclassifies intent. | Pilot MVP | Rule-first routing, feature flag, constrained labels, safe unknown fallback. |
| Local tests drift from production infra. | Pilot MVP | Real Postgres and Redis through Docker Compose locally and in CI. |
| Stale docs create implementation contradictions. | Pilot MVP | Archived spec is historical; living docs are canonical. |
