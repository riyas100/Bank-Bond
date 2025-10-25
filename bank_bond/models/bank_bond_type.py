# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class BankBondType(models.Model):
    _name = 'bank.bond.type'
    _description = 'Bank Bond Type'

    name = fields.Char(required=True, copy=False, string='Name')
    notes = fields.Html(string='Notes')
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.user.company_id
    )
