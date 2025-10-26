# Password Policy Documentation

## 1. Purpose

This document defines the password requirements and validation logic for our web application. It ensures that all user passwords meet strong security standards to protect accounts from unauthorized access.

---

## 2. Scope

This policy applies to:

* All user accounts in the system.
* Password reset and password creation forms.
* Automatically generated passwords via the system.

---

## 3. Password Requirements

Passwords must satisfy **all** of the following criteria:

| Requirement       | Description                                                                          |
| ----------------- | ------------------------------------------------------------------------------------ |
| Minimum Length    | At least **12 characters**.                                                          |
| Lowercase Letter  | At least **one lowercase letter** (`a-z`).                                           |
| Uppercase Letter  | At least **one uppercase letter** (`A-Z`).                                           |
| Special Character | At least **one special character** from the allowed set: `!@#$%^&*()-_=+[]{};:,.<>?` |

✅ All requirements must be met for the password to be accepted.

---

## 4. Validation Logic

The system checks passwords dynamically during user input.

**Step-by-step logic:**

1. **Length Check:**

   * Password length is measured. Must be ≥ 12 characters.

2. **Character Type Checks:**

   * Lowercase: Regex `[a-z]`
   * Uppercase: Regex `[A-Z]`
   * Special character: Regex `[!@#$%^&*()\-\_=+\[\]{};:,.<>?]`

3. **Strength Meter (Optional UI):**

   * **Weak:** Only 1–2 criteria met
   * **Medium:** 3 criteria met
   * **Strong:** All 4 criteria met

4. **Password Match Check:**

   * Confirm password field must exactly match the new password.

---

## 5. Error Feedback

If a password does **not meet requirements**:

* User sees a list of unmet requirements with red text.
* Once all requirements are satisfied, the system shows a green “✅ All requirements met!” message.

---

## 6. Password Generation

Users can optionally generate a strong password automatically:

* Length: 16 characters
* Contains at least one lowercase, uppercase, number, and special character
* Randomly selected from: `abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()-_=+[]{};:,.<>?`

---

## 7. Submission Enforcement

On form submission:

* The system validates both requirements and match.
* Submission is blocked if any requirement fails or passwords do not match.
* User receives an alert: `"Salasanavaatimukset eivät täyty tai salasanat eivät täsmää!"`

---

## 8. Examples of Valid Passwords

* `ImeMunaaPetteriOrpo!` ✅
* `StrongPassword123!` ✅
* `Giraffe#Dance2025` ✅

---

## 9. Security Notes

* Passwords are **case-sensitive**.
* Only the specified special characters are allowed.
* System logs do **not** store passwords in plaintext.
