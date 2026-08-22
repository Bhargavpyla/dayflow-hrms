from odoo import api, fields, models


class DayflowSalaryComponent(models.Model):
    """A configurable salary component definition, e.g. Basic, HRA,
    Standard Allowance, Performance Bonus, LTA, Fixed Allowance, PF,
    Professional Tax — exactly the tab shown in the wireframe.

    NOTE: if your Odoo instance has hr_payroll (Enterprise), prefer
    hr.salary.rule instead — it does this natively with a formula editor.
    This model exists for Community-edition instances.
    """
    _name = 'dayflow.salary.component'
    _description = 'Dayflow Salary Component'
    _order = 'sequence'

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    code = fields.Char(required=True, help="e.g. BASIC, HRA, STD_ALLOW, PF_EMP")
    component_type = fields.Selection(
        [
            ('earning', 'Earning'),
            ('deduction', 'Deduction'),
            ('employer_contribution', 'Employer Contribution (informational only)'),
        ],
        default='earning', required=True,
        help="Earning/Deduction affect the employee's Net Pay. Employer "
             "Contribution (e.g. Employer PF) is money the company spends "
             "on top of salary — shown for transparency, never subtracted "
             "from what the employee actually receives."
    )
    computation_type = fields.Selection(
        [
            ('pct_wage', '% of Wage'),
            ('pct_basic', '% of Basic'),
            ('fixed', 'Fixed Amount'),
            ('remainder', 'Remainder (Wage minus all other components)'),
        ],
        default='pct_wage', required=True,
    )
    value = fields.Float(
        string='Rate / Amount',
        help="Percentage (e.g. 50 for 50%) or a fixed monthly amount, "
             "depending on Computation Type."
    )
    active = fields.Boolean(default=True)


class DayflowSalarySlip(models.Model):
    _name = 'dayflow.salary.slip'
    _description = 'Dayflow Salary Slip'
    _order = 'date_to desc'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', store=True)
    employee_id = fields.Many2one('hr.employee', required=True, ondelete='cascade')
    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)

    wage = fields.Monetary(
        string='Monthly Wage', required=True,
        help="Pulled from the employee's contract; base for all component calculations."
    )
    line_ids = fields.One2many('dayflow.salary.slip.line', 'slip_id', string='Components')

    # Attendance -> payroll linkage (wireframe requirement:
    # "unpaid leave or missing attendance days should reduce payable days")
    total_working_days = fields.Integer(compute='_compute_attendance_days', store=True)
    payable_days = fields.Integer(compute='_compute_attendance_days', store=True)

    gross_earnings = fields.Monetary(compute='_compute_totals', store=True)
    total_deductions = fields.Monetary(compute='_compute_totals', store=True)
    employer_cost = fields.Monetary(
        compute='_compute_totals', store=True,
        help="Company-side contributions (e.g. Employer PF) — informational, "
             "not subtracted from Net Pay."
    )
    net_pay = fields.Monetary(compute='_compute_totals', store=True)

    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('paid', 'Paid')],
        default='draft',
    )

    def _compute_name(self):
        for rec in self:
            rec.name = f"{rec.employee_id.name} - {rec.date_from} to {rec.date_to}" \
                if rec.employee_id and rec.date_from else 'New Slip'

    @api.depends('employee_id', 'date_from', 'date_to')
    def _compute_attendance_days(self):
        Attendance = self.env['hr.attendance']
        Leave = self.env['hr.leave']
        for rec in self:
            if not (rec.employee_id and rec.date_from and rec.date_to):
                rec.total_working_days = 0
                rec.payable_days = 0
                continue

            total_days = (rec.date_to - rec.date_from).days + 1
            rec.total_working_days = total_days

            present_days = Attendance.search_count([
                ('employee_id', '=', rec.employee_id.id),
                ('check_in', '>=', rec.date_from),
                ('check_in', '<=', rec.date_to),
                ('dayflow_status', 'in', ('present', 'half_day')),
            ])
            paid_leave_days = Leave.search_count([
                ('employee_id', '=', rec.employee_id.id),
                ('state', '=', 'validate'),
                ('holiday_status_id.name', 'not in', ('Unpaid Leave',)),
                ('date_from', '<=', rec.date_to),
                ('date_to', '>=', rec.date_from),
            ])
            # Unpaid leave / no attendance / no leave record = unpayable day.
            rec.payable_days = min(total_days, present_days + paid_leave_days)

    @api.depends('wage', 'line_ids.amount', 'line_ids.component_type')
    def _compute_totals(self):
        for rec in self:
            earnings = sum(l.amount for l in rec.line_ids if l.component_type == 'earning')
            deductions = sum(l.amount for l in rec.line_ids if l.component_type == 'deduction')
            employer = sum(l.amount for l in rec.line_ids if l.component_type == 'employer_contribution')
            rec.gross_earnings = earnings
            rec.total_deductions = deductions
            rec.employer_cost = employer
            # Employer contributions are company cost, not employee deductions —
            # they never subtract from what the employee actually receives.
            rec.net_pay = earnings - deductions

    def action_generate_lines(self):
        """Runs the configured dayflow.salary.component set against this
        slip's EFFECTIVE wage (monthly wage scaled by attendance), in
        sequence, so 'remainder' components can see the running total of
        everything computed before them — mirrors the wireframe's
        'Fixed Allowance = Wage - total of all other components', while
        also honoring 'unpaid leave / missing attendance reduces pay'."""
        Component = self.env['dayflow.salary.component']
        for rec in self:
            rec.line_ids.unlink()

            if rec.total_working_days:
                proration = rec.payable_days / rec.total_working_days
            else:
                proration = 0.0
            effective_wage = rec.wage * proration

            components = Component.search([('active', '=', True)], order='sequence')
            basic_amount = 0.0
            running_total = 0.0
            lines_vals = []
            for comp in components:
                if comp.computation_type == 'pct_wage':
                    amount = effective_wage * (comp.value / 100.0)
                elif comp.computation_type == 'pct_basic':
                    amount = basic_amount * (comp.value / 100.0)
                elif comp.computation_type == 'fixed':
                    # Fixed amounts (e.g. Professional Tax) are NOT prorated
                    # by attendance — they're flat regardless of days worked.
                    amount = comp.value
                else:  # remainder
                    amount = effective_wage - running_total

                if comp.code == 'BASIC':
                    basic_amount = amount
                if comp.component_type == 'earning':
                    running_total += amount

                lines_vals.append((0, 0, {
                    'component_id': comp.id,
                    'component_type': comp.component_type,
                    'amount': amount,
                }))
            rec.line_ids = lines_vals


class DayflowSalarySlipLine(models.Model):
    _name = 'dayflow.salary.slip.line'
    _description = 'Dayflow Salary Slip Line'

    slip_id = fields.Many2one('dayflow.salary.slip', required=True, ondelete='cascade')
    component_id = fields.Many2one('dayflow.salary.component', required=True)
    component_type = fields.Selection(
        [
            ('earning', 'Earning'),
            ('deduction', 'Deduction'),
            ('employer_contribution', 'Employer Contribution'),
        ], required=True,
    )
    amount = fields.Monetary()
    currency_id = fields.Many2one(related='slip_id.currency_id')