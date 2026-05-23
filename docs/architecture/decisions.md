# Architecture Decisions
### Why we made the choices we did | Read before suggesting alternatives

---

Each entry follows: **Context → Decision → Reasoning → Consequences → What we rejected and why.**

---

## ADR-001: WhatsApp as the Sole Patient-Facing Interface

**Context:** We needed a patient-facing channel for appointment booking, report delivery, and reminders in Tier 2 India, targeting clinics where patients are not app-savvy and clinic owners don't want to manage another app.

**Decision:** WhatsApp is the only patient-facing interface. There is no patient mobile app, no patient web portal, no SMS fallback in MVP.

**Reasoning:**
- India has 500M+ WhatsApp users; penetration in Tier 2 cities is near-universal
- Patients already use WhatsApp daily — zero onboarding friction
- Report PDFs delivered on WhatsApp are opened immediately; email is not
- Clinic owners already manage a WhatsApp Business number manually — we're upgrading the tool, not replacing a habit

**Consequences:**
- We are dependent on Meta's WhatsApp Cloud API availability and pricing
- Any patient without WhatsApp is excluded (acceptable for target market)
- All bot copy must work in Hinglish on a small mobile screen

**Rejected:**
- SMS: lower open rate, no document support, can't send PDFs
- In-app experience: too high a friction for Tier 2 patients and clinic staff
- Telegram/Signal: negligible adoption in Indian healthcare context

---

## ADR-002: FastAPI Over Django

**Context:** We needed a Python backend framework that handles async I/O well for WhatsApp webhooks (which must respond < 500ms) and has good ecosystem support for SQLAlchemy async.

**Decision:** FastAPI with async/await throughout.

**Reasoning:**
- Webhook endpoint must ACK within 20 seconds (WhatsApp requirement) — async is non-negotiable
- FastAPI's automatic OpenAPI docs speed up dashboard frontend integration
- Pydantic v2 validation built in — critical for validating malformed WhatsApp payloads
- Much lighter than Django for a webhook-heavy, not admin-heavy workload

**Consequences:**
- No free admin panel (unlike Django admin) — we build a minimal React dashboard instead
- Team needs to be comfortable with async Python patterns

**Rejected:**
- Django: overkill ORM, sync-first design causes friction with async webhook requirements
- Node/Express: valid alternative but Python chosen for async webhook ergonomics and the team's preferred backend stack
- NestJS: too much ceremony for the MVP timeline

---

## ADR-003: Redis from Day 1 (Not Just for Future Celery)

**Context:** Original spec considered Redis optional in MVP, to be added only when Celery was needed for background tasks.

**Decision:** Redis is mandatory infrastructure from the first commit.

**Reasoning:**
- Every incoming WhatsApp message triggers 3 DB reads: clinic config, conversation session, test catalog
- At 50 messages/hour per clinic × 10 clinics = 1,500 DB reads/hour just for lookups that change at most hourly
- Clinic config and test catalog are effectively static between admin actions — caching these eliminates 60%+ of hot-path DB load
- Conversation session cache (30-min TTL) matches the DB session expiry exactly — no cold-path inconsistency

**Consequences:**
- One more infrastructure dependency to manage
- Redis must be included in all environments (dev, test, production) — not optional

**Rejected:**
- In-memory dict cache (Python process-level): doesn't survive restarts, not safe for multi-worker deployments
- Database query caching only: PostgreSQL's query cache doesn't help for application-layer object construction cost

---

## ADR-004: Soft Delete on All Patient Data (Never Hard Delete)

**Context:** We need to handle cancellations, patient opt-outs, and clinic offboarding without data loss.

**Decision:** All patient, appointment, test booking, and recall data uses `deleted_at` / `deleted_by` soft delete. No `DELETE FROM` on these tables in application code.

**Reasoning:**
- DPDP Act 2023: data subject requests and audit trails require knowing what existed and when it was removed
- Clinic churn: if a clinic cancels and re-subscribes, their historical data should be recoverable
- Debugging: "why did this appointment get cancelled" is answerable only if the record exists
- Accidental deletion: soft delete allows recovery; hard delete is irreversible

**Consequences:**
- All standard queries must include `.where(Model.deleted_at.is_(None))` to exclude deleted rows
- Over time, tables accumulate soft-deleted rows — periodic archival to cold storage should be planned for year 2+

**Rejected:**
- Hard delete: irreversible, compliance risk, loss of debugging ability
- Separate archive tables: more complexity, joins become harder

---

## ADR-005: Feature Flags in clinics.settings JSONB (Not Code-Level Enum Checks)

**Context:** Different pricing plans (starter, clinic, diagnostic, chain) have different feature sets. We need to gate features like `broadcasts`, `gbp_autopilot`, and `home_collection` by plan.

**Decision:** Feature flags stored per-clinic in `clinics.settings.features` JSONB. All feature checks go through `require_feature(clinic_id, feature_name, db)`.

**Reasoning:**
- Plan checks scattered across codebase (`if clinic.plan == "diagnostic"`) are a maintenance nightmare — every plan change requires grep-and-replace
- JSONB flags can be toggled per-clinic for beta testing, special deals, or exception handling without a code deploy
- `require_feature()` centralizes the check and the HTTP 403 error response — consistency guaranteed

**Consequences:**
- Feature flags must be set correctly during onboarding (seed from plan defaults)
- Must remember to invalidate `clinic` Redis cache when flags are changed

**Rejected:**
- Hardcoded plan-level checks in each handler: causes regressions on every plan restructure
- Separate `plan_features` table: JSONB is simpler for the scale we're at; join overhead not worth it

---

## ADR-006: Conversation State in Postgres + Redis (Not In-Memory)

**Context:** We need to maintain conversation context across messages (e.g., a patient selects a test in message 1, then selects a slot in message 2 — message 2 needs to know what was selected in message 1).

**Decision:** Conversation session state is stored in `conversation_sessions` (Postgres) with a write-through Redis cache (30-min TTL).

**Reasoning:**
- In-memory state is lost on server restart or process crash — unacceptable for appointment-booking flows
- Redis alone (without DB persistence) loses state on Redis restart
- Postgres as source of truth + Redis as fast path gives us both durability and speed
- 30-minute TTL matches reasonable user behavior: if a patient hasn't responded in 30 min, the flow should restart

**Consequences:**
- Every session write must update both DB and Redis (write-through)
- Session read must check Redis first, fall back to DB, re-populate Redis on miss

**Rejected:**
- In-memory dict: process-unsafe, not multi-worker compatible
- Redis only: state lost on Redis restart or eviction
- JWT-embedded state: too large for WA messages, can't be updated mid-flow

---

## ADR-007: Meta WhatsApp Cloud API Direct (No BSP)

**Context:** WhatsApp Business API can be accessed directly via Meta's Cloud API or through a Business Solution Provider (BSP) like AiSensy, WATI, or Interakt, which add a layer of tooling and additional cost.

**Decision:** Use Meta Cloud API directly. No BSP.

**Reasoning:**
- BSPs charge ₹2,000–10,000/month on top of Meta's conversation costs — adds ₹24,000–1.2L/year per deployment for features we are building ourselves
- Direct API gives full control over webhook handling, template management, and phone number provisioning
- BSPs are designed for non-technical users building flows in their UI — we are building flows in code where a BSP's abstraction layer adds friction
- Meta's own documentation and SDKs are mature enough for direct integration

**Consequences:**
- We handle Meta's Embedded Signup flow ourselves for clinic onboarding (each clinic needs their own WABA)
- We manage phone number registration and template submission ourselves
- Slightly more initial setup complexity

**Rejected:**
- AiSensy/WATI: adds per-message cost and a dependency on a third party that doesn't add value for our use case
- Twilio WhatsApp: extra vendor layer, higher per-message cost, less direct access to Meta features

---

## ADR-008: Single Webhook URL for All Clinics (Multi-Tenant Routing)

**Context:** Each clinic has their own WhatsApp Business number. We need to decide if each clinic gets their own webhook endpoint or if all clinics share one.

**Decision:** One webhook URL for all clinics. Routing is done by `phone_number_id` field in the webhook payload.

**Reasoning:**
- Meta allows multiple phone numbers under one WABA app — all send to the same webhook
- Per-clinic webhook URLs would require dynamic subdomain routing and separate deployments — operational complexity not worth it
- `phone_number_id` in the payload uniquely identifies which clinic's number received the message — look up the clinic by this field on every request

**Consequences:**
- Clinic lookup by `phone_number_id` happens on every single incoming message — this is the most critical Redis cache hit (`get_clinic_cached(phone_number_id)`)
- If the cache is cold, one extra DB read per message — acceptable

**Rejected:**
- Per-clinic subdomains: operational complexity, DNS management, separate SSL certs per clinic
- Per-clinic API keys in URL path: less clean, requires more Meta configuration

---

## ADR-009: Supabase for MVP Storage and Database (Self-Host Later)

**Context:** For the pilot with one diagnostic centre, we need managed Postgres, file storage for PDFs, and potentially auth — without infrastructure management overhead.

**Decision:** Use Supabase for MVP: managed Postgres, Supabase Storage for PDFs, Supabase Auth if needed.

**Reasoning:**
- Free tier is generous enough for a 60-day pilot (500MB DB, 1GB storage, 50K MAU)
- Built-in RLS dashboard makes multi-tenant policy setup visual and verifiable
- Storage signed URLs are built in — no custom S3 presigning code needed for MVP
- Can migrate to self-hosted Postgres + S3 without changing application code (same interfaces)

**Consequences:**
- Vendor lock-in risk is low — Supabase is Postgres under the hood; migration is `pg_dump` + S3 bucket copy
- Supabase Storage signed URL generation is slightly different from AWS S3 — abstract behind `app/services/storage.py` to make future migration seamless

**Rejected:**
- Self-hosted Postgres from Day 1: unnecessary operational burden for a 60-day pilot
- AWS RDS + S3: higher cost, more setup, overkill before product-market fit is proven

---

## ADR-010: APScheduler for MVP (Celery Later)

**Context:** We need scheduled jobs for reminders, recalls, review requests, and daily digests.

**Decision:** APScheduler (in-process, AsyncIOScheduler) for MVP. Migrate to Celery + Redis for production scale.

**Reasoning:**
- APScheduler requires zero additional infrastructure — it runs inside the FastAPI process
- For a 60-day pilot with one clinic, APScheduler handles the load trivially
- The upgrade path to Celery is straightforward — job logic stays the same, only the execution mechanism changes
- Redis is already provisioned (ADR-003) so Celery infrastructure cost is near-zero when we need it

**Consequences:**
- APScheduler does not distribute across multiple worker processes — only works reliably in single-worker deployments
- A process crash will skip in-progress jobs — jobs are designed idempotently so they recover on next run
- This is the one piece that will require refactoring when we scale beyond single-instance

**Rejected:**
- Celery from Day 1: adds `celery beat` process + worker process management overhead before we know we need it
- Cron jobs (OS-level): harder to manage, no Python async context, separate from application deploy

---

## ADR-011: Hinglish as Default Language

**Context:** The target users are patients and clinic owners in Tier 2 Indian cities (Bhopal, Indore, Nagpur, Lucknow).

**Decision:** Default language is Hinglish (Hindi written in Roman script). All default message templates are in Hinglish. Pure Hindi (Devanagari) and English are supported as per-clinic settings.

**Reasoning:**
- Hinglish is the natural register for informal digital communication in urban/semi-urban India
- Devanagari Hindi reduces by ~40% the percentage of patients who can type back comfortably on WhatsApp
- Pure English excludes a large portion of the target patient demographic
- Clinic owners themselves use Hinglish in their existing WhatsApp communications

**Consequences:**
- All message strings live in `app/templates/hinglish.py` (default), `hindi.py`, and `english.py`
- Language selection is per-clinic in `clinics.settings.language`
- UI labels in the web dashboard are English (for clinic owners/staff managing the system)

**Rejected:**
- English-only: excludes core demographic
- Pure Hindi only: typing friction, mixed-script input issues on mobile keyboards
- Per-patient language detection: over-engineering for MVP

---

## HOW TO USE THIS FILE

Before suggesting an alternative architecture, library, or design pattern, check if it conflicts with an existing ADR. If you believe an ADR should be revisited, add an entry at the bottom:

```markdown
## ADR-012: [Title]
**Supersedes:** ADR-00X (if applicable)
**Context:** ...
**Decision:** ...
**Reasoning:** ...
**Consequences:** ...
**Rejected:** ...
```

Do not silently override a decision in an ADR. Update the document.

---

## ADR-012: LLM Provider Abstraction With Groq Default

**Context:** The archived spec named a different LLM vendor for intent fallback and review replies, but the project direction is now Groq. We still want to avoid hard-coding provider-specific SDKs throughout flows and services.

**Decision:** Use a small provider abstraction in `app/services/llm_service.py`, with Groq as the default provider. Public app functions are provider-neutral: `classify_intent()` and `draft_review_reply()`.

**Reasoning:**
- Flow code should depend on project behavior, not a specific vendor SDK.
- Groq provider, model, timeout, and API key can be changed through `.env`.
- A small abstraction preserves future flexibility without adding a framework.
- Tests can mock `app.services.llm_service` and never hit a real provider.

**Consequences:**
- Active docs and code must not refer to any non-Groq provider as the selected provider.
- `.env.example` must include `LLM_PROVIDER`, `LLM_MODEL`, and `GROQ_API_KEY`.
- LLM fallback remains feature-flagged and never runs before rule-based routing.

**Rejected:**
- Groq SDK imported directly in flows: creates vendor coupling across the app.
- Full multi-provider framework: too much complexity for the Pilot MVP.

---

## ADR-013: Diagnostics-Only Pilot MVP

**Context:** The full SaaS spec supports GP clinics and diagnostic centers. The pilot target is one diagnostics clinic, and the critical value loop is test booking, home collection, report delivery, reminders, and repeat care.

**Decision:** Pilot MVP is diagnostics-only for conversation flows. Appointment, doctor, and slot data models remain in the Pilot MVP schema, but GP appointment booking flows are Post-pilot.

**Reasoning:**
- Diagnostics workflows validate the initial business case fastest.
- GP appointment flows add state-machine and routing complexity before the pilot needs it.
- Keeping appointment tables in the schema avoids a disruptive schema expansion later.

**Consequences:**
- Intent routing prioritizes diagnostics intents for Pilot MVP clinics.
- Appointment APIs and WhatsApp booking flows are tracked in backlog.
- Mixed clinic routing is Post-pilot.

**Rejected:**
- Building GP appointment flows in Pilot MVP: larger scope and slower pilot launch.
- Removing appointment tables entirely: creates unnecessary schema churn later.

---

## ADR-014: Railway Pilot, Hetzner Post-Pilot

**Context:** The pilot needs fast deployment with low operational overhead, but production should have a clear path to lower-cost self-hosted infrastructure.

**Decision:** Railway is the Pilot MVP deployment path. Hetzner plus Docker Compose is documented from day one as the Post-pilot production path.

**Reasoning:**
- Railway is faster for the first clinic.
- Hetzner gives a lower-cost path once operations stabilize.
- Documenting both now prevents hidden deployment assumptions.

**Consequences:**
- Pilot runs one Railway web replica because APScheduler is in-process.
- CI/CD docs cover both local CI and GitHub Actions with real Postgres/Redis.
- Scheduler worker migration is required before multi-replica production.

**Rejected:**
- Hetzner from day one: slows pilot validation.
- Railway-only docs: hides production migration requirements.
