# Dayflow on Odoo — Requirement → Module Mapping

**Strategy:** Don't rebuild what Odoo already has. Configure/extend native apps, and write custom code only for the gaps. This maximizes what you can demo in hackathon time.

## 1. Authentication & Authorization

| Requirement | Odoo Answer | Build? |
|---|---|---|
| Sign up (Employee ID, email, password, role) | `auth_signup` module (built-in portal signup) + custom Employee ID field on `res.users`/`hr.employee` | Light — add Employee ID field, wire signup flow |
| Email verification | `auth_signup` supports this via mail templates + SMTP config | Config only |
| Password security rules | Odoo has password policy settings (Settings → General → Users) | Config only |
| Role-based access (Admin/HR vs Employee) | Odoo's existing groups: `hr.group_hr_manager` (Admin/HR Officer), `base.group_user` (Employee) | Config only — just assign groups |
| Sign in, error handling, redirect to dashboard | Native Odoo login | None |

## 2. Dashboards

| Requirement | Odoo Answer | Build? |
|---|---|---|
| Employee dashboard (Profile/Attendance/Leave cards + alerts) | Odoo's **Employees** app has a personal profile view, but the "quick card" dashboard feel isn't native | **Custom** — small OWL/kanban dashboard view |
| Admin dashboard (employee list, attendance, approvals) | Native: Employees app list view, Attendance app, Time Off app "Approvals" | Config only |

## 3. Employee Profile

| Requirement | Odoo Answer | Build? |
|---|---|---|
| View personal/job details, salary, documents, photo | `hr.employee` model already has all these fields (`image_1920`, contract info, documents via Attachments) | Config only |
| Employee edits limited fields, Admin edits all | Odoo record rules already restrict self-editable fields; can tighten further | Light — record rule tweak |

## 4. Attendance

| Requirement | Odoo Answer | Build? |
|---|---|---|
| Check-in/check-out, daily/weekly view | `hr_attendance` module — native | Config only |
| Status: Present / Absent / **Half-day** / **Leave** | Native Attendance only tracks check-in/out (derives Present/Absent). Half-day and Leave aren't native attendance states | **Custom** — computed status field cross-referencing `hr.leave` |
| Employee sees own only, Admin sees all | Native record rules | Config only |

## 5. Leave & Time-Off

| Requirement | Odoo Answer | Build? |
|---|---|---|
| Apply for leave (type, date range, remarks) | `hr_holidays` module — native, full workflow | Config only |
| Approve/reject, comments, status (Pending/Approved/Rejected) | Native `hr.leave` states + chatter comments | Config only |
| Reflects in records immediately | Native | None |

## 6. Payroll

| Requirement | Odoo Answer | Build? |
|---|---|---|
| Employee read-only payroll view | `hr_payroll` (Enterprise) gives full payslips. Community edition payroll is limited | **Decision point** — see below |
| Admin manages salary structure | `hr_payroll` / `hr.contract` | Config, or light custom model if using Community |

**Payroll decision:** If you're on Odoo Community (no `hr_payroll`), don't try to build full payroll — build a lightweight custom `hr.salary.slip` model with basic fields (basic pay, deductions, net pay, read-only for employees). Full payroll engines are not a good use of hackathon time.

## 7. Notifications / Alerts / Analytics (bonus points from the PS)

| Requirement | Odoo Answer | Build? |
|---|---|---|
| Email & notification alerts | Odoo `mail` module + **Automation Rules** (Settings → Technical → Automation) — e.g. auto-email on leave approval/rejection | Config + a couple of automation rules |
| Analytics & reports (salary slips, attendance) | Odoo's built-in pivot/graph views on Attendance and Time Off; PDF reports via QWeb | Config + one custom QWeb report template if time allows |

## Suggested build order (fastest demo path)
1. Install & config `hr`, `hr_attendance`, `hr_holidays` (+ `hr_payroll` if Enterprise) — get native flows working end-to-end.
2. Custom module `dayflow_hrms`:
   - Attendance status field (Present/Absent/Half-day/Leave)
   - Employee dashboard view (quick-access cards)
   - Automation rules for email alerts on leave approval/rejection
   - (Stretch) lightweight payslip model if Community edition
3. Polish: QWeb report for salary slip / attendance summary, dashboard analytics.

This way your demo shows a fully working HRMS where ~70% is Odoo's proven native functionality and ~30% is your differentiated custom work — which is exactly what judges want to see (you're not fighting the framework, you're extending it intelligently).

## Addendum: business rules from the Excalidraw wireframe

The wireframe (`Human_Resource_Management_System_-_8_hours.excalidraw`) is the *real* functional spec — more precise than the PDF. Key deltas:

1. **No self-signup.** Only Admin/HR create employee accounts. Login ID is auto-generated: `OI` + first 2 letters of first name + first 2 letters of last name + joining year + zero-padded serial number for that year (e.g. `OIJODO20220001`). Password is system-generated on creation; employee changes it after first login. Implemented in `hr_employee.py` (`_dayflow_generate_login_id`, `action_dayflow_provision_user`).
2. **Salary is a genuine rule engine, not flat fields.** Wage → Basic (% of wage) → HRA (% of Basic) → Standard Allowance / Performance Bonus / LTA (% of wage or Basic) → Fixed Allowance (= wage − sum of everything else, the remainder) → PF (12% employee + 12% employer, on Basic) → Professional Tax (flat ₹200/month). This is structurally identical to Odoo's native `hr.salary.rule` engine (Enterprise `hr_payroll`) — **if your team has Enterprise access, this entire tab can likely be configuration, not custom code.** Implemented as a from-scratch engine (`dayflow.salary.component` + `dayflow.salary.slip`) for Community-edition parity.
3. **Attendance drives payroll.** Payable days = present/half-day attendance + paid leave days, capped at total days in the period. Unpaid leave or missing attendance silently reduces payable days. Implemented in `_compute_attendance_days`.
4. **Employee status icons on cards:** 🟢 present, ✈️ on leave, 🟡 absent (no check-in AND no leave applied). Refine the dashboard kanban's decoration logic to combine `hr.attendance` + `hr.leave` state, not just attendance alone.
5. **Fixed profile tabs:** About, Skills, Resume, Private Info, Security, Salary Info (Salary Info tab visible to Admin only — use `groups="hr.group_hr_user"` on that page in the employee form view). This is mostly re-skinning Odoo's native employee form tabs.
6. **Three leave types, exactly:** Paid Time Off, Sick Leave (requires an attachment — certificate), Unpaid Leave. Seeded in `data/salary_and_leave_seed_data.xml`.
7. **Admin employee-card click → profile opens read-only**, not the edit form. Handle via a dedicated read-only form view (all fields `readonly="1"`) reached only from the Admin's employee list/kanban, while HR's own edit access stays on the normal form.
8. **Check-in/out is a systray widget** with a live red→green status dot — this is Odoo's native Attendance kiosk/systray (`hr_attendance`'s "Attendance" app icon in the top bar). No custom code needed, just enable the app for all employees.

None of these change the overall module boundaries from the table above — they mostly tighten *how* the Employee, Attendance, and Payroll pieces need to behave. The updated `dayflow_hrms` module (see zip) now implements #1–#3 in code; #4–#8 are view/config work worth doing next given remaining time.
