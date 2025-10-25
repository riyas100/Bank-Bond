# -*- coding: utf-8 -*-
import logging
from odoo.fields import Command
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class BankBondInterestLine(models.Model):
    _name = 'bank.bond.interest.line'
    _description = 'BankBondInterestLine'

    bond_id = fields.Many2one('bank.bond', string='Bank Bond', required=True, ondelete='cascade')
    interest_rate = fields.Float(string='Interest Rate', related='bond_id.interest_rate', store=True)
    from_date = fields.Date(string='From Date', required=True)
    to_date = fields.Date(string='To Date', required=True)
    effective_days = fields.Integer("Effective Days")
    interest_period = fields.Selection(string='Interest Period', related='bond_id.interest_period', store=True)
    interest_amount = fields.Float(string='Interest Amount', required=True)
    state = fields.Selection([('draft', 'Draft'), ('posted', 'Posted')], default='draft')
    move_id = fields.Many2one('account.move', string='Journal Entry', copy=False)

    @api.model
    def _cron_bank_bond_interest_post(self):
        lines_to_post = self.search([('state', '=', 'draft'), ('to_date', '<', fields.Date.today())])
        for line in lines_to_post:
            # Logic to post entry
            line_vals = [
                Command.create(
                    {
                        "name": f"{line.bond_id.display_name}",
                        "partner_id": line.bond_id.bank_partner_id and line.bond_id.bank_partner_id.id or False,
                        "account_id": line.bond_id.interest_debit_account_id and line.bond_id.interest_debit_account_id.id,
                        "debit": line.interest_amount,
                    },
                ),
                Command.create(
                    {
                        "name": f"{line.bond_id.display_name}",
                        "partner_id": False,
                        "account_id": line.bond_id.interest_credit_account_id and line.bond_id.interest_credit_account_id.id,
                        "credit": line.interest_amount,
                    },
                ),
            ]
            move_id = self.env["account.move"].create(
                {
                    "company_id": line.bond_id.company_id and line.bond_id.company_id.id,
                    "move_type": "entry",
                    "ref": f"{line.bond_id.display_name} - Interest posting",
                    "journal_id": line.bond_id.interest_journal_id and line.bond_id.interest_journal_id.id,
                    "date": fields.Date.today(),
                    "line_ids": line_vals,
                }
            )
            move_id.action_post()

            line.write({
                'move_id': move_id and move_id.id,
                'state': 'posted'
            })
        return True
