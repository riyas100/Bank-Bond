# -*- coding: utf-8 -*-

import logging
import calendar
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from odoo import models, fields, api, _
from odoo.fields import Command
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)
STATE = [
    ('draft', 'Draft'),
    ('submitted', 'Submitted'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
    ('issued', 'Issued'),
]
ISSUANCE_TYPE = [
    ('at_face_value', 'At Face Value'),
    ('face_value_plus_premium', 'Face Value + Premium'),
    ('with_a_discount', 'With a Discount')
]

INTEREST_PERIOD = [('monthly', 'Monthly'), ('quarterly', 'Quarterly'), ('half_yearly', 'Half Yearly'),
                   ('yearly', 'Yearly')]


class BankBond(models.Model):
    _name = 'bank.bond'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Bank Bond'


    name = fields.Char(string='Name', default=_("New"), required=True)
    bond_number = fields.Char(required=True, copy=False, string='Bank Bond Number', tracking=True)
    bond_type_id = fields.Many2one('bank.bond.type', company_dependent=True, string='Bond Type', tracking=True)
    bank_id = fields.Many2one('res.bank', required=True, string='Issuing Bank', tracking=True)
    bank_partner_id = fields.Many2one('res.partner', string='Bank Partner', tracking=True)
    beneficiary_id = fields.Many2one('res.partner', required=True, string='Beneficiary', tracking=True)
    purchase_id = fields.Many2one('purchase.order', string='Purchase Order (PO) Reference', tracking=True)
    document_reference = fields.Char(string='Document Reference', tracking=True)
    project_id = fields.Many2one('project.project', string='Project', tracking=True)
    department_id = fields.Many2one('hr.department', string='Department', tracking=True)
    company_id = fields.Many2one(
        string='Company',
        comodel_name='res.company',
        required=True,
        default=lambda self: self.env.user.company_id,
        tracking=True

    )
    currency_id = fields.Many2one('res.currency', required=True, string='Currency',

                                  default=lambda self: self.env.user.company_id.currency_id,
                                  help='Currency in which the bond is issued', tracking=True)

    state = fields.Selection(STATE, string='State', default='draft', readonly=True, copy=False, index=True,
                             tracking=True)


    amount = fields.Monetary(string='Bond Amount', currency_field='currency_id', required=True,
                             help="Total value of the bond", tracking=True)
    bank_account_id = fields.Many2one('account.account', string='Bank Account',
                                      help='Account which the bond amount needs to receive', tracking=True)
    bond_liability_account_id = fields.Many2one('account.account', check_company=True,
                                                domain=[('account_type', '=', 'liability_payable')],
                                                string='Bond Liability Account',
                                                help="At the time of issuance, this account will be credited",
                                                tracking=True)

    issuance_type = fields.Selection(ISSUANCE_TYPE, default='at_face_value', string='Issuance Type', required=True)

    bond_fee_amount = fields.Monetary(string='Bond Fee', currency_field='currency_id',
                                      help="Any bank processing fees / Fee charged for issuing the bond", tracking=True)
    bond_fee_account_id = fields.Many2one('account.account', check_company=True, string='Bond Fee Account',
                                          tracking=True)
    bond_fee_counter_account_id = fields.Many2one('account.account', check_company=True,
                                                  string='Bond Fee Counter Account', tracking=True)

    premium_bond_payable_account_id = fields.Many2one('account.account', check_company=True,
                                                      domain=[('account_type', '=', 'liability_payable',)],
                                                      string='Premium Bond Payable Account', tracking=True)
    premium_bond_payable_amount = fields.Monetary(string='Premium Bond Payable Amount', currency_field='currency_id',
                                                  help="Amount payable for premium bond", tracking=True)

    discount_account_id = fields.Many2one('account.account', check_company=True,
                                          domain=[('account_type', '=', 'expense')], string='Discount Account',
                                          tracking=True)
    discount_amount = fields.Monetary(string='Discount Amount', currency_field='currency_id',
                                      help="Amount for discount", tracking=True)

    issue_date = fields.Date(string='Issue Date', required=True, help="Date on which the bond is issued", tracking=True)
    maturity_date = fields.Date(string='Maturity Date', required=True, help="Date on which the bond matures",
                                tracking=True)
    move_id = fields.Many2one('account.move', string='Journal Entry', copy=False)


    bond_renewal_ids = fields.One2many('bank.bond.renewal', 'bond_id', 'Renewal Details', copy=False)


    interest_period = fields.Selection(INTEREST_PERIOD, string='Interest Period', required=True,
                                       default='monthly',
                                       help="Interest period for the bond", tracking=True)
    interest_rate = fields.Float(string='Interest Rate', digits=(16, 2), help="Interest rate for the bond",
                                 tracking=True)
    bond_interest_line_ids = fields.One2many('bank.bond.interest.line', 'bond_id', 'Interest Lines', copy=False)
    interest_journal_id = fields.Many2one('account.journal', string='Account Journal', copy=False)
    interest_debit_account_id = fields.Many2one('account.account', string='Debit Account', copy=False, required=True)
    interest_credit_account_id = fields.Many2one('account.account', string='Credit Account', copy=False, required=True)



    bond_maturity_reminder_days = fields.Integer(
        string="Notification Days Before Bond Maturity",
        default=lambda self: self.env.user.company_id.bond_maturity_reminder_days)
    bond_maturity_reminder_users = fields.Many2many('res.users',
                                                    default=lambda
                                                        self: self.env.user.company_id.bond_maturity_reminder_users,
                                                    string='Notification Users')
    additional_maturity_reminder_emails = fields.Char(
        string="Additional Maturity Reminder Emails",
        default=lambda self: self.env.user.company_id.additional_maturity_reminder_emails)







    @api.depends('company_id')
    def _compute_show_send_for_approval_btn(self):
        for bond in self:
            bond.show_send_for_approval_btn = bond.company_id.is_bank_bond_approval_need

    @api.depends('approval_request_id', 'approval_request_id.current_approver_id')
    def compute_current_approver(self):
        for record in self:
            record.current_approver_id = record.approval_request_id and record.approval_request_id.current_approver_id and record.approval_request_id.current_approver_id.id or False

    @api.depends('approval_request_id', 'approval_request_id.request_status')
    def check_approval_state(self):
        for rec in self:
            if rec.approval_request_id:
                string = "Bank Bond Approval Request"
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

    @api.model
    def get_email_cc(self):
        """
        Get the email CC recipients for a bank bond.

        This method retrieves the email addresses of users specified in the
        'bond_maturity_reminder_users' field of a bank bond. It ensures that
        the method is called on a single record and returns a comma-separated
        string of email addresses of the related partners.

        Returns:
            str: Comma-separated email addresses of reminder users.
        """

        self.ensure_one()
        return ','.join(self.bond_maturity_reminder_users.partner_id.mapped('email'))

    @api.depends('bond_number')
    def _compute_display_name(self):
        """
        Compute display name of bank bond.

        The display name of a bank bond is composed of its bond number and its name.
        This method is decorated with @api.depends('bond_number') to ensure that it is
        called whenever the bond number is changed. The display name is then computed
        by concatenating the bond number and the name separated by a hyphen.
        """
        for bond in self:
            bond.display_name = f"{bond.bond_number} - {bond.name}"

    @api.model
    def _get_bonds_to_notify(self):
        """
        Retrieve bank bonds that need to be notified based on their maturity date.

        This method filters bank bonds to find those whose maturity date is
        equal to today's date plus the number of reminder days specified in
        each bond's 'bond_maturity_reminder_days' field.

        Returns:
            recordset: A recordset of bank bond objects that are due for notification.
        """

        today = fields.Date.today()
        all_bank_bonds = self.search([])
        bank_bonds_to_notify = all_bank_bonds.filtered(
            lambda bond: (today + relativedelta(days=bond.bond_maturity_reminder_days)) == bond.maturity_date)
        return bank_bonds_to_notify

    @api.model
    def _generate_maturity_date_mail_activity(self):
        """
        Generate mail activity for bank bond maturity date reminder.

        This method is used in the scheduled action to generate mail activity
        for bank bonds that are due for maturity date reminder. It creates
        a mail activity for each user specified in the 'bond_maturity_reminder_users'
        field of each bank bond that needs to be reminded. The activity is
        created with the note that contains the name and the number of the
        bond and the maturity date.
        """
        activity_type_id = self.env.ref('bank_bond.bank_bond_maturity_date_followup').id
        bonds_to_notify = self._get_bonds_to_notify()

        for bond in bonds_to_notify:
            existing_activities = self.env['mail.activity'].search([
                ('res_id', '=', bond.id),
                ('res_model', '=', 'bank.bond'),
                ('activity_type_id', '=', activity_type_id),
            ])

            if not existing_activities:
                activity_vals = []
                for user in bond.bond_maturity_reminder_users:
                    vals = {
                        'activity_type_id': activity_type_id,
                        'note': _(f"{bond.name}-{bond.bond_number} will be matured on {bond.maturity_date}"),
                        'user_id': user.id,
                        'res_id': bond.id,
                        'res_model_id': self.env['ir.model']._get('bank.bond').id,
                        'date_deadline': bond.maturity_date,
                    }
                    activity_vals.append(vals)
                self.env['mail.activity'].create(activity_vals)

    def _send_mail_maturity_date_reminder(self):
        bonds_to_notify = self._get_bonds_to_notify()
        for bond in bonds_to_notify:
            template_id = self.env.ref('bank_bond.bank_bond_maturity_date_followup_mail_template')
            template_id.send_mail(bond.id, force_send=True)

    @api.model
    def _cron_bank_bond_maturity_date_alert(self):

        """
        Cron job to alert users about bank bond maturity dates.

        This method executes scheduled actions to send email reminders and
        generate mail activities for bank bonds that are nearing their
        maturity date. It ensures that users specified in the bond's
        reminder settings are notified in advance.

        Returns:
            bool: True if the cron job executed successfully.
        """

        self._send_mail_maturity_date_reminder()
        self._generate_maturity_date_mail_activity()
        return True

    @api.model_create_multi
    def create(self, vals_list):
        """
        Override to generate sequence for bank bond number if not provided.
        """
        for vals in vals_list:
            if vals.get('name', _("New")) == _("New"):
                vals['name'] = self.env['ir.sequence'].next_by_code('bank.bond') or _("New")
        return super().create(vals_list)

    @api.onchange('bank_account_id')
    def onchange_bank_account_id(self):
        """
        Onchange for bank account to set the counter account for bond fee.
        If the bank account is set, then the counter account for bond fee is set to the same bank account.
        """
        for rec in self:
            if rec.bank_account_id:
                rec.bond_fee_counter_account_id = rec.bank_account_id

    @api.onchange('issuance_type')
    def onchange_issuance_type(self):
        """
        Onchange for issuance type to clear the fields based on the selection.

        If the issuance type is 'Face Value + Premium', then the fields 'Discount Amount' and 'Discount Account'
        are cleared. If the issuance type is 'With a Discount', then the fields 'Premium Bond Payable Amount' and
        'Premium Bond Payable Account' are cleared. If the issuance type is neither of the above, then both the above
        fields are cleared.
        """
        for rec in self:
            if rec.issuance_type == 'face_value_plus_premium':
                rec.discount_amount = 0.00
                rec.discount_account_id = False
            elif rec.issuance_type == 'with_a_discount':
                rec.premium_bond_payable_amount = 0.00
                rec.premium_bond_payable_account_id = False
            else:
                rec.premium_bond_payable_amount = rec.discount_amount = 0.00
                rec.premium_bond_payable_account_id = rec.discount_account_id = False

    @api.constrains('issuance_type', 'premium_bond_payable_amount', 'discount_amount',
                    'premium_bond_payable_account_id', 'discount_account_id')
    def _check_constrains(self):
        """
        Constrains to check the required fields based on issuance type.
        """
        for rec in self:
            if rec.maturity_date <= rec.issue_date:
                raise ValidationError(_('Maturity Date must be greater than Issue Date!'))

            if rec.amount == 0.00:
                raise ValidationError(
                    _('Bond Amount must be greater than 0.00!'))

            if not rec.bank_account_id:
                raise ValidationError(
                    _('Bond Account must be set!'))

            if not rec.bond_liability_account_id:
                raise ValidationError(
                    _('Bond Liability Account must be set!'))

            if rec.interest_rate <= 0.00:
                raise ValidationError(
                    _('Bond Interest Rate must be greater than 0.00!'))

            if rec.issuance_type == 'face_value_plus_premium':
                if not rec.premium_bond_payable_amount:
                    raise ValidationError(
                        _('Premium bond payable amount must be set for issuance type "Face Value + Premium".'))

                if not rec.premium_bond_payable_account_id:
                    raise ValidationError(
                        _('Premium bond payable account must be set for issuance type "Face Value + Premium".'))

            if rec.issuance_type == 'with_a_discount':
                if not rec.discount_amount:
                    raise ValidationError(_('Discount amount must be set for issuance type "With a Discount".'))

                if not rec.discount_account_id:
                    raise ValidationError(_('Discount account must be set for issuance type "With a Discount".'))

    def action_send_for_approval(self, approval_type_id, date, requested_by, remarks, approvers):
        """
        Method to send a bank bond approval request. It creates an approval request
        with the given details and adds the approvers to the request. The method
        also posts a message on the bank bond record with the approval request id.
        The state of the bank bond is changed to 'submitted'.
        :param approval_type_id: The id of the approval type.
        :type approval_type_id: int
        :param date: The date of the approval request.
        :type date: str
        :param requested_by: The user who is requesting the approval.
        :type requested_by: int
        :param remarks: The remarks for the approval request.
        :type remarks: str
        :param approvers: The approvers for the approval request.
        :type approvers: list
        :return: None
        """
        for bond in self:
            category_id = approval_type_id
            attachments = self.env['ir.attachment'].search(
                [('res_model', '=', 'bank.bond'), ('res_id', '=', bond.id)])
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
                        str(self.env.user.name), category_id.name, bond.beneficiary_id.name) + '\n Comments:' + str(
                        remarks)
                else:
                    reason = ("%s send a %s for Customer %s") % (
                        str(self.env.user.name), category_id.name, bond.beneficiary_id.name)
                name = ("Bond Approval for %s") % (bond.name)
                vals = {
                    'name': name,
                    'request_owner_id': self.env.user.id,
                    'category_id': category_id.id,
                    'bank_bond_id': bond.id,
                    'company_id': bond.company_id.id,
                    'partner_id': bond.beneficiary_id.id,
                    'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'approver_ids': approvers_dict,
                    'amount': bond.amount,
                    'currency_id': bond.currency_id.id,
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
                comment = "Bond Approval for " + bond.name + " has been submitted!"
                bond.update({'approval_request_id': approval_data.id,
                             'state': 'submitted',
                             })
                bond.message_post(body=_('%s') % (comment))



    def action_recall_approval_request(self):
        """
        Recall the Bank Bond Approval Request and reset the state of the Bank Bond to 'draft'.
        This method is used to cancel the approval request and reset the Bank Bond to its draft state.
        """
        for bond in self:
            if bond.approval_request_id:
                bond.approval_request_id.action_cancel()
                bond.action_set_to_draft()
                comment = f"Approval Request has be recalled by {self.env.user.name}"
                bond.message_post(body=_('%s') % comment)

    def action_set_to_draft(self):
        """
        Set the Bank Bond state to 'draft'.
        This method is used to change the state of the Bank Bond to 'draft' after it has been recalled or cancelled.
        It will also reset the approval_request_id to False.
        """
        for bond in self:
            bond.unlink_journal_entry()
            bond.write({
                'state': 'draft',
                'approval_request_id': False
            })

    def action_set_to_issued(self):
        """
        Set the Bank Bond state to 'issued'.
        This method is used to change the state of the Bank Bond to 'issued' after approval.
        """
        for bond in self:
            bond.write({
                'state': 'issued',
            })

    @api.ondelete(at_uninstall=False)
    def _unlink_except_draft(self):
        for bond in self:
            if bond.state != 'draft':
                raise UserError(_('You cannot delete a bank bond that is not in draft state.'))

    def prepare_journal_entry_vals(self):
        """
        Prepares the journal entry line values based on the bond issuance type.

        The method returns a list of dictionaries each containing the values
        for a journal entry line. The dictionaries should have the following keys:
        - name: the description of the journal entry line
        - partner_id: the partner id of the bank
        - account_id: the account id of the journal entry line
        - debit: the debit amount of the journal entry line
        - credit: the credit amount of the journal entry line

        The method takes into account the bond fee amount and discounts the amount
        accordingly. It also handles the case where the bond is issued with a premium.

        :return: a list of dictionaries each containing the values for a journal entry line
        """
        line_vals = []

        if self.issuance_type == 'at_face_value':
            line_vals = [
                Command.create(
                    {
                        "name": f"{self.display_name}",
                        "account_id": self.bank_account_id and self.bank_account_id.id,
                        "debit": self.amount,
                    },
                ),
                Command.create(
                    {
                        "name": f"{self.display_name}",
                        "partner_id": self.bank_partner_id and self.bank_partner_id.id or False,
                        "account_id": self.bond_liability_account_id and self.bond_liability_account_id.id,
                        "credit": self.amount,
                    },
                ),
            ]
        elif self.issuance_type == 'face_value_plus_premium':
            line_vals = [
                Command.create(
                    {
                        "name": f"{self.display_name}",
                        "account_id": self.bank_account_id and self.bank_account_id.id,
                        "debit": self.amount,
                    },
                ),
                Command.create(
                    {
                        "name": f"{self.display_name}",
                        "partner_id": self.bank_partner_id and self.bank_partner_id.id or False,
                        "account_id": self.bond_liability_account_id and self.bond_liability_account_id.id,
                        "credit": self.amount - self.premium_bond_payable_amount,
                    },
                ),
                Command.create(
                    {
                        "name": f"{self.display_name} Premium Amount Line",
                        "partner_id": self.bank_partner_id and self.bank_partner_id.id or False,
                        "account_id": self.premium_bond_payable_account_id and self.premium_bond_payable_account_id.id,
                        "credit": self.premium_bond_payable_amount,
                    },
                ),
            ]
        elif self.issuance_type == 'with_a_discount':
            line_vals = [
                Command.create(
                    {
                        "name": f"{self.display_name}",
                        "account_id": self.bank_account_id and self.bank_account_id.id,
                        "debit": self.amount - self.discount_amount,
                    },
                ),
                Command.create(
                    {
                        "name": f"{self.display_name} - Discount Line",
                        "account_id": self.discount_account_id and self.discount_account_id.id,
                        "debit": self.discount_amount,
                    },
                ),
                Command.create(
                    {
                        "name": f"{self.display_name}",
                        "partner_id": self.bank_partner_id and self.bank_partner_id.id or False,
                        "account_id": self.bond_liability_account_id and self.bond_liability_account_id.id,
                        "credit": self.amount,
                    },
                ),
            ]
        if self.bond_fee_amount > 0.00:
            bond_fee_vals = [
                Command.create(
                    {
                        "name": f"{self.display_name} Bond Fee",
                        "partner_id": self.bank_partner_id and self.bank_partner_id.id or False,
                        "account_id": self.bond_fee_account_id and self.bond_fee_account_id.id,
                        "debit": self.bond_fee_amount,
                    },
                ),
                Command.create(
                    {
                        "name": f"{self.display_name} Bond Fee",
                        "account_id": self.bond_fee_counter_account_id and self.bond_fee_counter_account_id.id,
                        "credit": self.bond_fee_amount,
                    },
                ),
            ]
            line_vals = line_vals + bond_fee_vals

        return line_vals

    def unlink_journal_entry(self):
        """
        Unlinks the journal entry (account move) related to the current bank bond.

        This method is used to cancel a bank bond. It sets the journal entry to draft mode and then unlinks it.
        """
        for rec in self:
            if rec.move_id:
                rec.move_id.button_draft()
                rec.move_id.unlink()

    def action_issue_bond(self):
        """
        Issues a bank bond by creating an account move (journal entry).

        This method performs the following steps:
        1. Retrieves the bank bond journal.
        2. Prepares the journal entry line values based on the bond issuance type.
        3. Creates an account move with the specified details.
        4. Posts the created account move to finalize the transaction.
        5. Updates the bank bond state to 'issued'.

        The function ensures that the necessary accounting entries are made
        to reflect the issuance of the bank bond in the company's financial records.
        """

        bank_bond_journal_id = self.env.ref("bank_bond.bank_bond_account_journal", raise_if_not_found=True)
        line_vals = self.prepare_journal_entry_vals()
        move_id = self.env["account.move"].create(
            {
                "company_id": self.company_id and self.company_id.id,
                "move_type": "entry",
                "ref": f"{self.display_name}",
                "journal_id": bank_bond_journal_id and bank_bond_journal_id.id,
                "date": fields.Date.today(),
                "line_ids": line_vals,
            }
        )
        if move_id:
            self.write({
                'move_id': move_id
            })
            move_id.action_post()
        self.action_set_to_issued()


    @api.model
    def days_from_month_start(self, d):
        """
        Calculates the number of days from the first day of a given month to a given date d.

        Args:
            d (datetime.date): The date for which to calculate the offset from the first day of the month.

        Returns:
            int: The number of days from the first day of the month to the given date.
        """
        first_day_of_month = d.replace(day=1)
        return (d - first_day_of_month).days

    @api.model
    def days_until_end_of_month(self, given_date):
        """
        Calculates the number of days until the end of a given month, given a date.

        Args:
            given_date (datetime.date): The date for which to calculate the offset until the end of the month.

        Returns:
            int: The number of days until the last day of the month.
        """
        year = given_date.year
        month = given_date.month
        _, last_day = calendar.monthrange(year, month)
        last_day_of_month = date(year, month, last_day)
        return (last_day_of_month - given_date).days

    @api.model
    def get_last_date(self, d):
        """
        Returns the last date of the month for a given date.

        Args:
            d (datetime.date): The date for which to find the last day of the month.

        Returns:
            datetime.date: The last day of the month corresponding to the given date.
        """

        num_days_in_month = calendar.monthrange(d.year, d.month)[1]
        return d.replace(day=num_days_in_month)

    @api.model
    def get_num_days_in_month(self, d):
        """
        Returns the number of days in a given month.

        Args:
            d (datetime.date): The date for which to find the number of days in the month.

        Returns:
            int: The number of days in the month corresponding to the given date.
        """
        num_days_in_month = calendar.monthrange(d.year, d.month)[1]
        return num_days_in_month

    @api.model
    def is_first_day_of_month(self, date_obj):
        """
        Checks if a given date is the first day of a month.

        Args:
            date_obj (datetime.date or str): The date to check. If a string, it should be in the format '%Y-%m-%d'.

        Returns:
            bool: True if the given date is the first day of the month, False otherwise.
        """
        if isinstance(date_obj, date):
            return date_obj.day == 1
        elif isinstance(date_obj, str):
            date_obj = fields.Date.from_string(date_obj)
            return date_obj.day == 1

    @api.model
    def is_last_day_of_month(self, date_obj):
        if isinstance(date_obj, date):
            return date_obj.day == self.get_num_days_in_month(date_obj)
        elif isinstance(date_obj, str):
            date_obj = fields.Date.from_string(date_obj)
            return date_obj.day == self.get_num_days_in_month(date_obj)

    def is_issue_month(self, d, renewal=False):
        """
        Determines if a given date falls within the issue month of the bond.

        Args:
            d (datetime.date): The date to check against the bond's issue date.

        Returns:
            bool: True if the given date is within the same month and year as the bond's issue date, False otherwise.
        """
        if renewal:
            return d.month == renewal.previous_maturity_date.month and d.year == renewal.previous_maturity_date.year
        return d.month == self.issue_date.month and d.year == self.issue_date.year

    def is_maturity_month(self, d):
        """
        Determines if a given date falls within the maturity month of the bond.

        Args:
            d (datetime.date): The date to check against the bond's maturity date.

        Returns:
            bool: True if the given date is within the same month and year as the bond's maturity date, False otherwise.
        """

        return d.month == self.maturity_date.month and d.year == self.maturity_date.year



    def post_interest_line(self):
        try:
            self._create_interest_line(self.issue_date, self.maturity_date)
        except Exception as e:
            _logger.warning(f"An Exception has occured : {e}")

    def _create_interest_line(self, Issue_Date, Maturity_Date, Renewal=False):
        self.ensure_one()
        Interest_Obj = self.env['bank.bond.interest.line']
        monthly_interest = self.amount * (self.interest_rate / 100) / 12
        quarterly_interest = self.amount * (self.interest_rate / 100) / 4
        half_yearly_interest = self.amount * (self.interest_rate / 100) / 2
        yearly_interest = self.amount * (self.interest_rate / 100)

        VALS = []

        if self.interest_period == 'monthly':
            start_date = Issue_Date

            def append_single_month_interest(start, end, days, amt):
                VALS.append(
                    {
                        'bond_id': self.id,
                        'interest_rate': self.interest_rate,
                        'interest_period': self.interest_period,
                        'from_date': start,
                        'to_date': end,
                        'effective_days': days,
                        'interest_amount': amt
                    })

            while start_date < Maturity_Date:
                if self.is_issue_month(start_date,Renewal):
                    is_first_day_of_month = self.is_first_day_of_month(start_date)
                    if is_first_day_of_month:
                        append_single_month_interest(start_date, self.get_last_date(start_date),
                                                     self.get_num_days_in_month(start_date), monthly_interest)

                    else:
                        effective_days = self.days_until_end_of_month(start_date)
                        amount = monthly_interest * (effective_days / self.get_num_days_in_month(start_date))
                        append_single_month_interest(start_date, self.get_last_date(start_date),
                                                     effective_days, amount)
                elif self.is_maturity_month(start_date):
                    effective_days = self.days_from_month_start(Maturity_Date)
                    amount = monthly_interest * (effective_days / self.get_num_days_in_month(start_date))
                    append_single_month_interest(start_date, self.get_last_date(start_date), effective_days, amount)

                else:
                    effective_days = self.get_num_days_in_month(start_date)
                    append_single_month_interest(start_date, self.get_last_date(start_date), effective_days,
                                                 monthly_interest)

                start_date = start_date.replace(day=1) + relativedelta(months=1)
        elif self.interest_period == 'quarterly':
            start_date = Issue_Date

            def append_quarter_year_interest(start, end, days, amt):
                VALS.append(
                    {
                        'bond_id': self.id,
                        'interest_rate': self.interest_rate,
                        'interest_period': self.interest_period,
                        'from_date': start,
                        'to_date': end,
                        'effective_days': days,
                        'interest_amount': amt
                    })

            while start_date < Maturity_Date:
                day_after_quarter_year = start_date + relativedelta(months=3)
                if day_after_quarter_year <= Maturity_Date:
                    days = (day_after_quarter_year - start_date).days
                    append_quarter_year_interest(start_date, day_after_quarter_year, days, quarterly_interest)
                else:
                    days = (Maturity_Date - start_date).days
                    amount = monthly_interest * (days / 30)
                    append_quarter_year_interest(start_date, Maturity_Date, days, amount)

                start_date = day_after_quarter_year
        elif self.interest_period == 'half_yearly':
            start_date = Issue_Date

            def append_half_year_interest(start, end, days, amt):
                VALS.append(
                    {
                        'bond_id': self.id,
                        'interest_rate': self.interest_rate,
                        'interest_period': self.interest_period,
                        'from_date': start,
                        'to_date': end,
                        'effective_days': days,
                        'interest_amount': amt
                    })

            while start_date < Maturity_Date:
                day_after_half_year = start_date + relativedelta(months=6)
                if day_after_half_year <= Maturity_Date:
                    days = (day_after_half_year - start_date).days
                    append_half_year_interest(start_date, day_after_half_year, days, half_yearly_interest)
                else:
                    days = (Maturity_Date - start_date).days
                    amount = monthly_interest * (days / 30)
                    append_half_year_interest(start_date, Maturity_Date, days, amount)

                start_date = day_after_half_year
        elif self.interest_period == 'yearly':
            start_date = Issue_Date

            def append_year_interest(start, end, days, amt):
                VALS.append(
                    {
                        'bond_id': self.id,
                        'interest_rate': self.interest_rate,
                        'interest_period': self.interest_period,
                        'from_date': start,
                        'to_date': end,
                        'effective_days': days,
                        'interest_amount': amt
                    })

            while start_date < Maturity_Date:
                day_after_year = start_date + relativedelta(years=1)
                if day_after_year <= Maturity_Date:
                    days = (day_after_year - start_date).days
                    append_year_interest(start_date, day_after_year, days, yearly_interest)
                else:
                    days = (Maturity_Date - start_date).days
                    amount = monthly_interest * (days / 30)
                    append_year_interest(start_date, Maturity_Date, days, amount)

                start_date = day_after_year
        Interest_Obj.create(VALS)
        Interest_Obj._cron_bank_bond_interest_post()
