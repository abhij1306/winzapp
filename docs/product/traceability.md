# Requirements Traceability

This file proves that the archived spec has not been lost. Every major requirement area is mapped to active requirements, execution tasks, or backlog.

## Spec Section Coverage

| Archived Spec Section | Living Requirement IDs | Execution Location | Phase |
|---|---|---|---|
| 1. Project Overview and NFRs | PRD-001..006, NFR-001..012 | `docs/project/tasks.md`, `docs/project/backlog.md` | Mixed |
| 2. Tech Stack Decision Matrix | PLAT-001..013 | `docs/architecture/decisions.md` | Mixed |
| 3. Recommended Stack | PLAT-001..013 | `docs/architecture/decisions.md` | Mixed |
| 4. System Architecture | DATA-001..013, WA-001..010, FLOW-001..010 | `docs/architecture/*.md` | Mixed |
| 5. Database Schema | DATA-001..013 | S1 tasks | Pilot MVP |
| 6. WhatsApp Cloud API Integration | WA-001..010 | S1/S2 tasks | Mixed |
| 7. Conversation Flows | FLOW-001..010 | S2 tasks, backlog for GP/mixed flows | Mixed |
| 8. Backend API Endpoints | API-001..014 | S1/S3 tasks, backlog for non-MVP APIs | Mixed |
| 9. Caching Layer | PLAT-003, DATA-006 | S1 tasks | Pilot MVP |
| 10. Scheduler and Automation | AUTO-001..009 | S3 tasks, backlog for appointment/GBP jobs | Mixed |
| 11. Report PDF Delivery | REP-001..007 | S2/S3 tasks | Mixed |
| 12. GBP Autopilot | API-012, AUTO-008, UI-007 | `docs/project/backlog.md` | Post-pilot |
| 13. Feature Flags | PLAT-005, FLOW-002, DATA-002 | S1 tasks | Pilot MVP |
| 14. Admin Dashboard | UI-001..009 | S3 tasks, backlog for non-MVP pages | Mixed |
| 15. Onboarding Flow | API-014, UI-009, WA-010 | `docs/project/backlog.md` | Post-pilot |
| 16. Security and Compliance | SEC-001..008 | S1/S2/S3 tasks | Mixed |
| 17. Observability and Alerting | OBS-001..007 | S1/S3 tasks | Pilot MVP |
| 18. Environment Variables and Config | PLAT-007, SEC-004, SEC-005 | S1 tasks, CI/CD docs | Pilot MVP |
| 19. Deployment | PLAT-012, PLAT-013 | S1 tasks, CI/CD docs | Mixed |
| 20. MVP Scope | `docs/product/mvp-scope.md` | S1/S2/S3 tasks | Pilot MVP |
| 21. File and Folder Structure | PLAT-001..013 | S1 tasks | Pilot MVP |
| 22. Third-Party Services | PLAT-006..013 | ADRs, CI/CD docs, backlog | Mixed |
| 23. Testing Strategy | NFR-005, SEC-008, OBS-003 | All task DoD | Pilot MVP |
| 24. INVARIANTS.md | Root `INVARIANTS.md` | Every task | Pilot MVP |
| 25. Launch Checklist | CI/CD and runbook docs | `docs/ci-cd/release-checklist.md` | Pilot MVP |

## Endpoint Traceability

| Endpoint | Requirement | Phase | Execution Task |
|---|---|---:|---|
| `GET /health` | OBS-003 | Pilot MVP | S1-T01, S1-T13 |
| `GET /webhook/whatsapp` | WA-001 | Pilot MVP | S1-T10 |
| `POST /webhook/whatsapp` | WA-002..005 | Pilot MVP | S1-T10 |
| `POST /auth/otp/send` | API-002 | Pilot MVP | S3-T01 |
| `POST /auth/otp/verify` | API-002 | Pilot MVP | S3-T01 |
| `GET /api/v1/clinics/{id}` | API-003 | Pilot MVP | S3-T02 |
| `PUT /api/v1/clinics/{id}` | API-003 | Pilot MVP | S3-T02 |
| `GET /api/v1/clinics/{id}/test-bookings` | API-004 | Pilot MVP | S3-T03 |
| `POST /api/v1/clinics/{id}/test-bookings` | API-004 | Pilot MVP | S2-T04/S3-T03 |
| `PUT /api/v1/clinics/{id}/test-bookings/{booking_id}` | API-004 | Pilot MVP | S3-T03 |
| `POST /api/v1/clinics/{id}/test-bookings/{booking_id}/report` | API-004, REP-001 | Pilot MVP | S3-T04 |
| `DELETE /api/v1/clinics/{id}/test-bookings/{booking_id}` | API-004 | Pilot MVP | S2-T06/S3-T03 |
| `POST /api/v1/report-ready` | API-005, REP-002 | Pilot MVP | S2-T06 |
| `GET /api/v1/clinics/{id}/patients` | API-006 | Pilot MVP | S3-T05 |
| `GET /api/v1/clinics/{id}/patients/{patient_id}` | API-006 | Pilot MVP | S3-T05 |
| `PUT /api/v1/clinics/{id}/patients/{patient_id}` | API-006 | Pilot MVP | S3-T05 |
| `GET /api/v1/clinics/{id}/tests` | API-007 | Pilot MVP | S3-T06 |
| `POST /api/v1/clinics/{id}/tests` | API-007 | Pilot MVP | S3-T06 |
| `PUT /api/v1/clinics/{id}/tests/{test_id}` | API-007 | Pilot MVP | S3-T06 |
| `DELETE /api/v1/clinics/{id}/tests/{test_id}` | API-007 | Pilot MVP | S3-T06 |
| `GET /api/v1/clinics/{id}/failed-messages` | API-008 | Pilot MVP | S3-T07 |
| `POST /api/v1/clinics/{id}/failed-messages/{id}/retry` | API-008 | Pilot MVP | S3-T07 |
| `GET /api/v1/clinics/{id}/stats` | API-009 | Pilot MVP | S3-T08 |
| Appointment endpoints | API-010 | Post-pilot | Backlog |
| Slot endpoints | API-011 | Post-pilot | Backlog |
| Review GBP approval endpoints | API-012 | Post-pilot | Backlog |
| Broadcast endpoints | API-013 | Post-pilot | Backlog |
| Clinic registration endpoints | API-014 | Post-pilot | Backlog |

## Known Deliberate Deferrals

- Razorpay is Post-pilot.
- Password-protected PDFs are Post-pilot.
- GBP autopilot is Post-pilot and feature-flagged.
- GP appointment booking flows are Post-pilot.
- Mixed clinic routing is Post-pilot.
- Broadcasts are Post-pilot.
