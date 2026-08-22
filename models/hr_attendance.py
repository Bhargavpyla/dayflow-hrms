from odoo import api, fields, models


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    dayflow_status = fields.Selection(
        [
            ('present', 'Present'),
            ('absent', 'Absent'),
            ('half_day', 'Half-day'),
            ('leave', 'Leave'),
        ],
        string='Status',
        compute='_compute_dayflow_status',
        store=True,
        help="Derived status combining check-in/out data with approved leave records."
    )

    @api.depends('check_in', 'check_out', 'employee_id')
    def _compute_dayflow_status(self):
        Leave = self.env['hr.leave']
        for record in self:
            if not record.check_in:
                record.dayflow_status = 'absent'
                continue

            check_date = record.check_in.date()

            # Was the employee on approved leave that day?
            on_leave = Leave.search_count([
                ('employee_id', '=', record.employee_id.id),
                ('state', '=', 'validate'),
                ('date_from', '<=', check_date),
                ('date_to', '>=', check_date),
            ])
            if on_leave:
                record.dayflow_status = 'leave'
                continue

            if not record.check_out:
                # Still checked in / incomplete day — treat as present so far
                record.dayflow_status = 'present'
                continue

            worked_hours = (record.check_out - record.check_in).total_seconds() / 3600.0
            # Simple heuristic: less than half a standard 8h day = half-day.
            # Tune this threshold to your company's actual work schedule (hr.resource.calendar).
            if worked_hours < 4:
                record.dayflow_status = 'half_day'
            else:
                record.dayflow_status = 'present'


class HrEmployeeAttendanceSummary(models.Model):
    """Convenience model powering the weekly attendance view on the dashboard."""
    _inherit = 'hr.employee'

    dayflow_today_status = fields.Selection(
        related='attendance_state',
        string='Today (raw check-in state)',
    )
