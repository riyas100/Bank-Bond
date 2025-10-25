# -*- coding: utf-8 -*-

{
    'name': "Bank Bond Management",
    'version': '18.0',
    'author': 'Muhammed Riyas',
    'category': 'Accounting',
    'license': 'LGPL-3',
    'sequence': 2,
    'summary': """
     Manage and track bank bonds, renewals, and compliance efficiently""",
    'description': """
        The Bank Bond Management module provides a complete solution for handling
        different types of bank bonds such as bid bonds, performance bonds, and retention bonds.
        Features include:
        - Bond registration and tracking
        - Automated expiry and renewal reminders
        - Integration with accounting and project modules
        - Comprehensive reporting and audit trail
        This module helps organizations maintain financial transparency and compliance.
    """,
    'depends': ['account_accountant', 'accountant','purchase', 'project','hr'],
    "data": [
        "data/ir_sequence_data.xml",
        "data/activity.xml",
      #  "data/cron.xml",
        "data/email_templates.xml",
        "data/account_journal.xml",
        "security/ir.model.access.csv",
        "security/rules.xml",
        "views/bank_bond_type_views.xml",
        "views/bank_bond_views.xml",
        "views/bank_bond_renewal_views.xml",
        "views/bank_bond_interest_line_views.xml",
        "views/menu.xml",
        "views/res_config_settings.xml",

    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': ['static/description/images/cover.png'],
}




