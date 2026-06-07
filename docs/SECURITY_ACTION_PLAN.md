# Internal Security Remediation Action Plan: Project "Miekkari"

**Status:** Draft / Urgent
**Severity:** Critical (Multiple Authorization & Authentication Failures)
**Last Updated:** June 7, 2026

## Executive Summary
A comprehensive security audit has revealed multiple critical vulnerabilities that allow for total system takeover, unauthorized resource consumption, and data manipulation. The most severe issue (Mass Assignment) permits any registered user to escalate their privileges to Global Administrator.

---

## Phase 1: Immediate Containment (Next 24 Hours)
*Goal: Close the most critical entry points for exploitation.*

### 1.1 Patch Mass Assignment (Vulnerability AUTH-MASS-ASSIGN-001)
- **Action:** Implement a strict allowlist in `mielenosoitukset_fi/users/BPs/auth.py` for both `settings_api` (v1) and `user_profile` (v2).
- **Detail:** Explicitly list allowed fields (e.g., `display_name`, `language`, `dark_mode`, `city`). Ensure all other fields are discarded before processing.
- **Verification:** Run the `tests/reproduce_mass_assignment.py` PoC to confirm it now fails.

### 1.2 Secure API Token Scopes (Vulnerability AUTH-TOKEN-SCOPE-002)
- **Action:** Update the token generation logic to strictly allowlist acceptable scopes.
- **Detail:** Block any scope containing `.admin` or `admin` unless the requesting user is already a verified global admin.

---

## Phase 2: Core Hardening (Next 72 Hours)
*Goal: Fix foundational security flaws and prevent session-based attacks.*

### 2.1 Implement CSRF Protection
- **Action:** Integrate `Flask-WTF` and enable `CSRFProtect`.
- **Detail:** Update all templates to include `{{ form.csrf_token() }}` or use the `X-CSRFToken` header for AJAX/JSON requests.

### 2.2 Correct Authorization Decorators (Vulnerability AUTH-SCOPED-ADMIN-003)
- **Action:** Refactor `has_admin_access` and `@admin_required` in `utils/wrappers.py`.
- **Detail:** Ensure global admin routes strictly require `global_admin=True` and do not accept regional/city-scoped grants.

### 2.3 Enforce Account Status (Vulnerability AUTH-BAN-BYPASS-004)
- **Action:** Override `is_active` in the `User` model (`models.py`) to return `not self.banned and self.active`.
- **Detail:** Flask-Login will automatically block sessions for users where `is_active` returns `False`.

---

## Phase 3: Secondary Risks & Cleanup (Next 7 Days)
*Goal: Sanitize inputs, secure secrets, and harden infrastructure.*

### 3.1 Input Sanitization & XSS Prevention
- **Action:** Audit all templates for `|safe`. Replace with a sanitizer (e.g., `Bleach`) for any user-generated content like demonstration descriptions.

### 3.2 JWT Purpose Separation (Vulnerability AUTH-TOKEN-PURPOSE-006)
- **Action:** Add a `typ` or `purpose` claim to all JWT tokens generated in `utils/auth.py`.
- **Detail:** Update verifiers to ensure an email confirmation token cannot be used for a password reset.

### 3.3 Environment & Infrastructure
- **Action:** Ensure `SECRET_KEY` has no default fallback in `config.py`.
- **Action:** Update `Caddyfile` to include HSTS and a restrictive Content Security Policy (CSP).

---

## Phase 4: Long-Term Assurance
*Goal: Establish a secure development lifecycle (SDLC).*

1. **Automated Scanning:** Integrate `bandit` (static analysis) and `safety` (dependency check) into the GitHub Actions CI pipeline.
2. **Database Audit:** Run a one-time script to audit the `users` collection for any accounts with `global_admin: True` that are not on the approved admin list.
3. **Security Training:** Review the "Pre-Dedupe Candidates" report with the development team to understand common pitfalls like Mass Assignment and JWT purpose confusion.

---
**Plan Prepared by:** Gemini CLI
**Verification Method:** Empirical PoC testing for all identified vulnerabilities.
