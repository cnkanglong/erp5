from Products.ERP5Form.Report import ReportSection

selection_columns = (
  ('title', 'Title',),
  ('int_index', 'Int Index',),
  ('parent_description', 'Description',),
  ('parent_comment', 'Comment',),
  ('parent_reference', 'Invoice Number',),
  ('specific_reference', 'Transaction Reference',),
  ('node_reference', 'Account Code',),
  ('node_title', 'Account Name',),
  ('node_account_type_title', 'Account Type',),
  ('node_financial_section_title', 'Financial Section',),
  ('section_title', 'Section',),
  ('payment_title', 'Section Bank Account',),
  ('payment_mode', 'Payment Mode',),
  ('mirror_section_title', 'Third Party',),
  ('mirror_payment_title', 'Third Party Bank Account',),
  ('mirror_section_region_title', 'Third Party Region',),
  ('function_reference',
      '%s Reference' % context.AccountingTransactionLine_getFunctionBaseCategoryTitle()),
  ('function_title',
      context.AccountingTransactionLine_getFunctionBaseCategoryTitle()),
  ('funding_reference', 'Funding Reference',),
  ('funding_title', 'Funding',),
  ('project_title', 'Project',),
  ('product_line', 'Product Line'),
  ('string_index', 'String Index'),
  ('date', 'Operation Date'),
  ('debit_price', 'Converted Debit'),
  ('credit_price', 'Converted Credit'),
  ('price', 'Converted Net'),
  ('currency', 'Accounting Currency'),
  ('debit', 'Debit'),
  ('credit', 'Credit'),
  ('quantity', 'Net'),
  ('resource', 'Transaction Currency'),
  ('translated_portal_type', 'Line Type'),
  ('parent_translated_portal_type', 'Transaction Type'),
  ('translated_simulation_state_title', 'State'),)


return [ReportSection(form_id='AccountingTransactionModule_viewAccountingLineReportReportSection',
                      selection_columns=selection_columns,
                      path=context.getPhysicalPath())]
