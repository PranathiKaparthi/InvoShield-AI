# InvoShield Assistant: build plan and codebase notes

This is the "Step 0" analysis from the master prompt, written before the agent was built, plus the
decisions taken. Branch: `feature/invoshield-assistant`.

## 1. Existing API (before this branch)

| Route | Auth | Returns |
|---|---|---|
| `POST /api/auth/register`, `POST /api/auth/login` | public | JWT + user |
| `GET /api/auth/me` | any user | profile |
| `POST /api/invoices/upload` | any user | full invoice detail (pipeline inline in the route) |
| `GET /api/invoices` | any user (user: own; reviewer: own org; admin: all) | paginated list |
| `GET/PUT /api/invoices/{id}` | GET any user, PUT admin/reviewer | detail / update + re-encrypt |
| `POST /api/invoices/{id}/validate` | any user | revalidated detail |
| `POST /api/invoices/{id}/approve` | admin/reviewer + Segregation of Duties | invoice |
| `POST /api/invoices/{id}/reject` | admin/reviewer | invoice |
| `GET /api/invoices/{id}/duplicates`, `/risk-analysis`, `/file` | any user | dup breakdown / risk reasons / file |
| `POST /api/ocr/process` | any user | raw OCR + parsed fields |
| `GET /api/dashboard/statistics`, `/analytics` | any user (scoped) | KPIs, charts |
| `/api/admin/users`, `/users/{id}/role`, `/audit-logs`, `/flagged` | admin | admin data |

## 2. Data model

`User` 1-n `Invoice` 1-n `InvoiceItem`, `ValidationResult`, `DuplicateCheck`, `FraudAlert`, `AuditLog`.
Sensitive fields (`gst_number`, `tax_id`, `bank_details`) are AES-256-GCM encrypted. Tenancy is by the
`organization` string on users and invoices.

## 3. Reused directly (no duplicated logic)

* OCR, extraction, validation, duplicate detection, fraud scoring, encryption, storage services.
* The upload pipeline and approve/reject logic were **moved out of the route handlers** into
  `app/services/invoice_pipeline.py` and `app/services/invoice_actions.py`. The web routes and the
  assistant now call the same functions, so RBAC and Segregation-of-Duties live in one place.

## 4. Gaps found, and what was done

| Gap | Resolution |
|---|---|
| No vendor/contact records, no phone numbers | `agent_contacts` table (vendor or staff, phone/email, verified flag, language) |
| No payment status | `invoices.payment_status` (unpaid/scheduled/paid) + `POST /api/invoices/{id}/mark-paid` |
| No record of where an invoice came from | `invoices.source_channel`, `invoices.source_contact_id` |
| **Extractor invents data** when a field can't be read (fake US address, IBAN, PO, a $1,250 total, sample line items) | New `demo_fallbacks` switch. The assistant always uses honest mode (empty -> reported as Missing). Web upload keeps old behaviour unless `EXTRACTION_DEMO_FALLBACKS=False` |
| Indian amounts (`Rs. 1,18,000.00`) not parsed; INR not detected from "Rs." | Fixed in the extractor |
| Fraud reasons always printed `$` | Uses the invoice's currency symbol |
| Tests wrote into the committed `invoshield.db` | `tests/conftest.py` uses a temp DB + storage |
| `invoshield.db` and uploaded invoices committed to git | Untracked and git-ignored |
| Demo passwords seeded everywhere | Seeded only when `APP_ENV` is not production; production uses `BOOTSTRAP_ADMIN_*` with forced password change |
| Default JWT/AES/MinIO secrets could reach production | Server refuses to start with them when `APP_ENV=production` |

## 5. Layout

```
backend/app/agent/
  core.py           agent loop (single entry point for every channel)
  tools.py          11 tools: schemas, validation, scoping, audit
  llm.py            Anthropic provider, offline demo provider, scripted test provider
  prompts.py        runtime system prompt
  identity.py       phone/email -> contact -> role
  policies.py       tool permissions, data scoping, redaction, untrusted wrapping, rate limit
  approval.py       YES/NO confirmations + approval queue
  delivery.py       redaction, WhatsApp 24h window, send, log, audit
  memory.py         conversations, messages, history, per-org settings
  notifications.py  template messages to vendors on approve/reject/paid
backend/app/channels/  base.py, mock.py, whatsapp.py, email.py, templates.py
backend/app/api/agent.py  webhooks + Assistant Inbox API
backend/scripts/   demo_assistant.py, email_poller.py
frontend/src/pages/AssistantInboxPage.tsx, ChangePasswordPage.tsx
```

## 6. New tables

`agent_contacts`, `agent_conversations`, `agent_messages`, `agent_approvals`, `agent_settings`.
New columns: `invoices.payment_status`, `invoices.source_channel`, `invoices.source_contact_id`,
`users.must_change_password`. Added automatically by `init_db()` (idempotent, SQLite and PostgreSQL).

## 7. Second pass: errors fixed

| Problem | Fix |
|---|---|
| Any logged-in user could open, download, re-validate or analyse **any** invoice by ID; reviewers could read/edit other companies' invoices | `load_invoice_for_user()` on every invoice route (404 outside your scope) |
| Anyone could self-register as **reviewer of an existing company** via the API | Joining an existing organization always starts as `user`; only a new organization's first account may be reviewer |
| Reviewers' dashboard activity feed showed every company's audit events | Scoped to the reviewer's organization |
| Rupee invoices displayed as dollars (₹2,83,500 shown as $283,500, or ×83 in INR view); dashboard added ₹ and $ together | Amounts converted from each invoice's own currency; dashboard totals normalised |
| Dashboard showed two made-up vendors when there was no data | Removed |
| Fraud thresholds treated ₹25,000 like $25,000 | Per-currency, configurable thresholds |
| Extractor invented values by default | `EXTRACTION_DEMO_FALLBACKS` now defaults to `False` |
| `smoke_test.py` failed on a fresh clone | Creates the database first |
| Stale duplicate `backend/services/` folder; unused imports/variables (Python and TypeScript) | Removed |
| Dashboard unusable on phones | Menu button + slide-out sidebar |
| Daily summary showed rupee vendor totals with a $ sign | Each vendor keeps its own currency |
| Assistant needed exact phrasing | Numbered menu, follow-up questions, everyday Hinglish/Tanglish and native-script keywords, plain-language replies |
