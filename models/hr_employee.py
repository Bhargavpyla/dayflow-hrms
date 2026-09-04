import re
from odoo import api, fields, models
from odoo.exceptions import UserError


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    dayflow_employee_id = fields.Char(
        string='Login ID',
        copy=False,
        readonly=True,
        help="Auto-generated: OI + first 2 letters of first name + first 2 letters "
             "of ladst name + year of joining + serial number for that year. "
             "e.g. OIJODO20220001"
    )
    dayflow_joining_year = fields.Integer(
        compute='_compute_dayflow_joining_year', store=True,
    )

    @api.depends('create_date')
    def _compute_dayflow_joining_year(self):
        for emp in self:
            ref_date = emp.create_date and emp.create_date.date()
            emp.dayflow_joining_year = ref_date.year if ref_date else fields.Date.today().year

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        for emp in employees:
            if not emp.dayflow_employee_id:
                emp.dayflow_employee_id = emp._dayflow_generate_login_id()
        return employees

    def _dayflow_generate_login_id(self):
        """OI + first 2 letters of first name + first 2 letters of last name
        + joining year + zero-padded serial number for that year.
        e.g. John Doe, joined 2022, 1st that year -> OIJODO20220001
        """
        self.ensure_one()
        name_parts = (self.name or 'XX XX').strip().split()
        first = name_parts[0] if name_parts else 'XX'
        last = name_parts[-1] if len(name_parts) > 1 else first
        code = re.sub(r'[^A-Za-z]', '', (first[:2] + last[:2])).upper().ljust(4, 'X')

        year = self.dayflow_joining_year or fields.Date.today().year

        # Serial number = count of employees already assigned an ID for this year, +1
        existing = self.search_count([
            ('dayflow_employee_id', 'like', f'OI%{year}%'),
            ('dayflow_joining_year', '=', year),
        ])
        serial = str(existing + 1).zfill(4)
        return f"OI{code}{year}{serial}"

    def action_dayflow_provision_user(self):
        """HR/Admin-only action: create the res.users login for this employee
        with an auto-generated password. Employees never self-register."""
        self.ensure_one()
        if not self.env.user.has_group('hr.group_hr_user'):
            raise UserError("Only HR Officers or Admins can provision employee logins.")
        if self.user_id:
            raise UserError("This employee already has a login.")
        if not self.work_email:
            raise UserError("Set a work email before provisioning a login.")

        temp_password = self.env['ir.sequence'].sudo().next_by_code(
            'dayflow.temp.password') or fields.Datetime.now().strftime('%y%m%d%H%M%S')

        user = self.env['res.users'].sudo().create({
            'name': self.name,
            'login': self.work_email,
            'email': self.work_email,
            'password': f"Dayflow@{temp_password}",
            'groups_id': [(4, self.env.ref('base.group_user').id)],
        })
        self.user_id = user.id
        # Odoo will prompt a password reset on first login when
        # action_reset_password() is called instead of a raw password set —
        # for a hackathon demo, sending the temp password via email is simpler:
        user.with_context(create_user=True).action_reset_password()
        return True
    dayflow_pending_leaves = fields.Integer(
        string='Pending Leave Requests',
        compute='_compute_dayflow_dashboard_counts',
    )
    dayflow_leave_balance = fields.Float(
        string='Leave Balance (days)',
        compute='_compute_dayflow_dashboard_counts',
    )

    def _compute_dayflow_dashboard_counts(self):
        Leave = self.env['hr.leave']
        Allocation = self.env['hr.leave.allocation']
        for emp in self:
            emp.dayflow_pending_leaves = Leave.search_count([
                ('employee_id', '=', emp.id),
                ('state', '=', 'confirm'),
            ])
            # In Odoo 17, remaining_leaves was removed from hr.employee.
            # Calculate remaining allocated days from approved allocations minus validated leaves:
            allocations = Allocation.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'validate'),
            ])
            total_allocated = sum(allocations.mapped('number_of_days'))
            leaves = Leave.search([
                ('employee_id', '=', emp.id),
                ('state', '=', 'validate'),
            ])
            total_taken = sum(leaves.mapped('number_of_days'))
            emp.dayflow_leave_balance = max(0.0, total_allocated - total_taken)

    def action_dayflow_open_attendance(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Attendance',
            'res_model': 'hr.attendance',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
        }

    def action_dayflow_open_leaves(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'My Leave Requests',
            'res_model': 'hr.leave',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
        }
