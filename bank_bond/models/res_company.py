# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class ResCompany(models.Model):
    _inherit = 'res.company'
    _description = 'ResCompany'

    bond_maturity_reminder_days = fields.Integer(
        string="Notification Days Before Bond Maturity",
        readonly=False)
    bond_maturity_reminder_users = fields.Many2many(
        'res.users',
        'bond_maturity_reminder_users_rel',
        'company_id',
        'user_id',
        readonly=False,
        string='Notification Users')
    additional_maturity_reminder_emails = fields.Char(
        string="Additional Maturity Reminder Emails",
        readonly=False)

    is_bank_bond_approval_need = fields.Boolean(
        string="Bank Bond Approval Needed?",
        readonly=False)

    is_bank_bond_renewal_approval_need = fields.Boolean(
        string="Bank Bond Renewal Approval Needed?",
        readonly=False)
