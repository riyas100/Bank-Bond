# -*- coding: utf-8 -*-


from odoo import api, exceptions, fields, models, _


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bond_maturity_reminder_days = fields.Integer(
        string="Notification Days Before Bond Maturity",
        readonly=False,
        related='company_id.bond_maturity_reminder_days')
    bond_maturity_reminder_users = fields.Many2many(
        related='company_id.bond_maturity_reminder_users',
        readonly=False,
        string='Notification Users')
    additional_maturity_reminder_emails = fields.Char(
        string="Additional Maturity Reminder Emails",
        related='company_id.additional_maturity_reminder_emails',
        readonly=False)
    is_bank_bond_approval_need = fields.Boolean(
        string="Bank Bond Approval Needed?",
        readonly=False,
        related='company_id.is_bank_bond_approval_need')

    is_bank_bond_renewal_approval_need = fields.Boolean(
        string="Bank Bond Renewal Approval Needed?",
        readonly=False,
        related='company_id.is_bank_bond_renewal_approval_need')
