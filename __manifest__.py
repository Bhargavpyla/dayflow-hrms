{
    'name': 'Dayflow HRMS',
    'version': '1.0',
    'summary': 'Dayflow: Every workday, perfectly aligned.',
    'description': """
        Custom extensions on top of Odoo's native HR apps to implement
        the Dayflow HRMS problem statement:
        - Attendance status (Present/Absent/Half-day/Leave)
        - Employee self-service dashboard
        - Leave approval email notifications
        - Lightweight payslip (Community edition fallback)
    """,
    'category': 'Human Resources',
    'author': 'Dayflow Team',
    'depends': ['hr', 'hr_attendance', 'hr_holidays', 'mail', 'base_automation'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/hr_attendance_views.xml',
        'views/hr_salary_slip_views.xml',
        'data/mail_template_data.xml',
        'data/automation_rules.xml',
        'data/salary_and_leave_seed_data.xml',
    ],
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
