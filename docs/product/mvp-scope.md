# Pilot MVP Scope

The Pilot MVP validates a diagnostics clinic workflow end to end. It is not a general clinic SaaS launch.

## Included

- WhatsApp webhook intake with signature verification, idempotency, write-first logging, and dead-lettering.
- Explicit patient consent flow before automated booking/report flows.
- Diagnostics test catalog, walk-in booking, home collection booking, cancellation, and report inquiry flows.
- Manual/offline payment handling only.
- Report upload and WhatsApp PDF delivery through signed URLs/documents.
- Recall scheduling and reminder automation for diagnostics tests.
- Fasting reminders, review requests, daily digest, scheduler heartbeat.
- Minimal owner/staff dashboard: OTP login, overview, test bookings, pending reports/upload, failed messages/retry, settings.
- Appointment, doctor, and slot data models for future clinic support.
- Groq-backed LLM fallback through `app/services/llm_service.py`, controlled by feature flag.
- Railway deployment with one web replica and in-process APScheduler.
- Real PostgreSQL and Redis in local development, local CI, and GitHub Actions.

## Excluded From Pilot MVP

- GP appointment booking WhatsApp flows.
- Mixed clinic routing where a single clinic offers both GP appointment and diagnostics workflows.
- Razorpay subscriptions or in-flow payment collection.
- Password-protected PDFs.
- GBP OAuth, review fetching, AI reply approval, or auto-posting.
- Broadcast campaigns.
- Automated clinic onboarding wizard and Meta Embedded Signup.
- Multi-replica production scaling.

## Pilot Success Metrics

- Inbound phone calls for test booking reduced by at least 50 percent.
- Report delivery is same-day through WhatsApp.
- Patient opt-in rate is at least 80 percent.
- Home collection no-show rate is below 10 percent.
- Clinic owner would pay for the service after the pilot.
