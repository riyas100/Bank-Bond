# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

STATE = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('done', 'Done'),
]


class BankBondRenewal(models.Model):
    _name = 'bank.bond.renewal'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'BankBondRenewal'

    _bond_id_domain = '''
            [('state', '=','issued'),('maturity_date', '<', context_today().strftime('%Y-%m-%d'))]
        '''

    name = fields.Char(string='Name', default=_("New"), required=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    bond_id = fields.Many2one('bank.bond', string='Bank Bond', required=True,
                              domain=_bond_id_domain)
    previous_maturity_date = fields.Date(string='Prev: Maturity Date', required=True)
    maturity_date = fields.Date(string='New Maturity Date', required=True, default=fields.Date.today() + relativedelta(
        years=1))  # Just for auto populate a date after 1 Year there is no any requirement
    state = fields.Selection(STATE, string='State', default='draft', readonly=True, copy=False, index=True,
                             tracking=True)
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        related='bond_id.company_id'
    )



    @api.model_create_multi
    def create(self, vals_list):

        """
        Override to generate sequence for bank bond renewal number if not provided.
        """

        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('bank.bond.renewal') or _("New")
        return super().create(vals_list)

    @api.onchange('bond_id')
    def _onchange_bond_id(self):
        for renewal in self:
            if renewal.bond_id:
                renewal.write({
                    'previous_maturity_date': renewal.bond_id.maturity_date,
                    'maturity_date': renewal.bond_id.maturity_date + relativedelta(years=1)
                })

    @api.depends('company_id')
    def _compute_show_send_for_approval_btn(self):
        for renewal in self:
            renewal.show_send_for_approval_btn = renewal.company_id.is_bank_bond_renewal_approval_need

    @api.depends('approval_request_id', 'approval_request_id.current_approver_id')
    def compute_current_approver(self):
        for record in self:
            record.current_approver_id = record.approval_request_id and record.approval_request_id.current_approver_id and record.approval_request_id.current_approver_id.id or False

    @api.depends('approval_request_id', 'approval_request_id.request_status')
    def check_approval_state(self):
        for rec in self:
            if rec.approval_request_id:
                string = "Bank Bond Renewal Approval Request"
                approver_ids = rec.approval_request_id.approver_ids
                approve_lst = approver_ids.filtered(lambda l: l.status == "approved").mapped(
                    'user_id.name')
                refuse_lst = approver_ids.filtered(lambda l: l.status == "refused").mapped(
                    'user_id.name')
                pending_lst = approver_ids.filtered(lambda l: l.status == "pending").mapped(
                    'user_id.name')
                if len(approve_lst) > 0:
                    string += " Approved by " + ",".join(approve_lst) + ' , '
                if rec.approval_request_id.request_status == 'pending' and len(pending_lst) > 0:
                    string += " Pending for " + ",".join(pending_lst) + ' , '
                if rec.approval_request_id.request_status == 'refused' and len(refuse_lst) > 0:
                    string += " Refused by " + ",".join(refuse_lst) + ' , '
                string = string[:-2]
                rec.approval_state = string
            else:
                rec.approval_state = False

    def action_send_for_approval(self, approval_type_id, date, requested_by, remarks, approvers):

        for renewal in self:
            category_id = approval_type_id
            attachments = self.env['ir.attachment'].search(
                [('res_model', '=', 'bank.bond.renewal'), ('res_id', '=', renewal.id)])
            approvers_dict = []
            for approver in approvers:
                apprval_line = category_id.approver_ids.filtered(lambda l: l.user_id == approver)
                required = apprval_line[0].required if apprval_line else False
                approvers_dict.append((0, 0, {
                    'user_id': approver.id,
                    'required': required,
                    'status': 'new'
                }))
            if category_id:
                if remarks:
                    reason = ("%s send a %s for Benificiary %s") % (
                        str(self.env.user.name), category_id.name,
                        renewal.bond_id.beneficiary_id.name) + '\n Comments:' + str(
                        remarks)
                else:
                    reason = ("%s send a %s for Customer %s") % (
                        str(self.env.user.name), category_id.name, renewal.bond_id.beneficiary_id.name)
                name = ("Bond Renewal Approval for %s") % (renewal.name)
                vals = {
                    'name': name,
                    'request_owner_id': self.env.user.id,
                    'category_id': category_id.id,
                    'bank_bond_renewal_id': renewal.id,
                    'company_id': renewal.company_id.id,
                    'partner_id': renewal.bond_id.beneficiary_id.id,
                    'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'approver_ids': approvers_dict,
                    'amount': renewal.bond_id.amount,
                    'currency_id': renewal.bond_id.currency_id.id,
                    'reason': reason
                }
                approval_data = self.env['approval.request'].create(vals)
                for attachment in attachments:
                    self.env['ir.attachment'].create({
                        'name': attachment.name,
                        'res_name': approval_data.name,
                        'type': 'binary',
                        'datas': attachment.datas,
                        'res_model': 'approval.request',
                        'res_id': approval_data.id,

                    })
                approval_data.action_confirm()
                comment = "Bond Renewal Approval for " + renewal.name + " has been submitted!"
                renewal.update({'approval_request_id': approval_data.id,
                                'state': 'submitted',
                                })
                renewal.message_post(body=_('%s') % (comment))




    def _update_bond_maturity_date(self):
        self.bond_id.maturity_date = self.maturity_date

    def action_set_to_draft(self):
        for bond in self:
            bond.write({
                'state': 'draft',
                'approval_request_id': False
            })

    def action_done(self):
        for renewal in self:
            renewal.bond_id._create_interest_line(self.previous_maturity_date, self.maturity_date)
            renewal._update_bond_maturity_date()
            renewal.write({'state': 'done'})

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft(self):
        for renewal in self:
            if renewal.state != 'draft':
                raise UserError(_('You cannot delete a bank bond renewal that is not in draft state.'))
