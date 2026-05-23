# Roadmap

## Phase 1: Pilot MVP Diagnostics Clinic

Goal: prove WhatsApp-native diagnostics booking and report delivery.

Milestones:

1. Core infrastructure deployable on Railway.
2. WhatsApp webhook receives, logs, routes, and responds safely.
3. Diagnostics test booking and home collection flows work.
4. Report upload/API delivery sends PDFs over WhatsApp.
5. Scheduler sends fasting reminders, recalls, review requests, daily digest, and heartbeat.
6. Minimal dashboard supports daily operations.
7. Pilot launch checklist passes.

## Phase 2: Post-Pilot SaaS Expansion

Goal: turn pilot into a repeatable product for multiple clinics.

Includes:

- GP appointment booking flows.
- Mixed clinic routing.
- Razorpay subscriptions.
- GBP autopilot.
- Password-protected PDFs.
- Broadcasts.
- Clinic onboarding wizard and Meta Embedded Signup.
- Hetzner/Docker Compose production deployment.
- Scheduler worker/Celery migration.

## Phase 3: Future/Backlog

Goal: deeper automation after repeatable SaaS operations exist.

Includes:

- Advanced analytics.
- Multi-branch clinic chains.
- More LIMS integrations.
- Data archival automation.
- Optional provider migration for LLM/storage/payment services.
