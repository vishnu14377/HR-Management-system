# Security Model

The sensitive data here is **rate / margin** (business-confidential) and
**work-authorization / PII** (compliance). This document describes how access is
enforced, the one known residual, and the go-live verification.

## Roles

| Role | Sees bench + requirements | Sees rate / margin | Edits |
|---|---|---|---|
| `Recruiter` | ✅ | ❌ | bench + requirements + submissions |
| `Bench Sales` | ✅ | ❌ | bench + requirements + submissions |
| `Recruiting Manager` | ✅ | ✅ (read + write) | everything |
| `Account Manager` | ✅ | ✅ (read only) | requirements + submissions |
| `HR Manager` (HRMS) | ✅ | ✅ (read + write) | employee master incl. PII |

## The rate/margin firewall (permission level 1)

Every rate field is defined at **permlevel 1**:

- `Client Requirement`: `bill_rate`, `max_bill_rate`, `pay_rate_target`
- `Submission`: `submitted_bill_rate`
- `Employee` (custom): `current_bill_rate`, `current_pay_rate`

Only `Recruiting Manager`, `Account Manager` (read), `HR Manager`, and
`System Manager` are granted permission at level 1. Frappe strips level-1 fields a
user cannot access from **the form, list view, report view, and API query results** —
so a recruiter cannot read rate/margin through any standard channel. Level-1 grants on
`Employee` are applied idempotently by
`racedog_hr/patches/v0_0_1/setup_roles_and_permissions.py`; on the custom DocTypes they
live in the DocType JSON `permissions`.

## Known residual (must be closed or accepted before go-live)

**Recruiters have `write` at permlevel 0 on `Employee`.** Frappe checks document-level
write at permlevel 0, so to let recruiters flip `deployment_status` / `availability_date`
in Desk they currently also *can* edit other level-0 native Employee fields (name,
department, contact — **not** rates, which are level 1). This is the PII-write breadth
the plan's judge flagged.

Two ways to close it (pick one before go-live):

1. **Raise sensitive native fields to a manager permlevel** via Property Setters shipped
   as fixtures (e.g. push SSN/DOB/bank fields to permlevel 1). Recruiters keep write@0 for
   the operational bench fields but lose write on the sensitive ones.
2. **Lock Employee to read-only for recruiters** and route bench edits through a
   whitelisted, role-checked, field-allowlisted server method (`update_bench`) that saves
   with `ignore_permissions` — the same method the Vue board uses. This is the tighter
   option; it just means recruiters edit bench state through the board/button, not the raw
   Employee form.

Until one is applied, treat recruiter Employee-write as an accepted, logged risk. The
rate/margin firewall (the business-critical one) is **not** affected by this residual.

## Other protections

- **PII exclusion from web/portal**: the custom DocTypes are Desk-only; none are
  published to the HRMS `/jobs` career portal or any Website route.
- **Double-submission / RTR**: enforced server-side in `Submission.validate()`, backed by
  a `(consultant, requirement)` composite index — not client-side only.
- **Soft-close over delete**: `Client Requirement` closes by status, preserving audit and
  metrics; only managers/System Manager hold `delete`.

## Go-live verification (do on the deployed instance)

1. As a `Recruiter`, confirm rate/margin is invisible in **form + list + report + API**
   for `Employee`, `Client Requirement`, and `Submission`.
2. Confirm the double-submission block and RTR warning fire.
3. Confirm no custom DocType is reachable unauthenticated (check `/app` vs `/`).
4. Rehearse a backup restore; confirm TLS before entering real rate/PII data.
5. Decide and apply one residual-closure option above (or sign off on accepting it).
