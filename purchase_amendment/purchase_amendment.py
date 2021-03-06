from datetime import *
import time
from osv import fields, osv
from tools.translate import _
import netsvc
import decimal_precision as dp
from itertools import groupby
from datetime import datetime, timedelta,date
from dateutil.relativedelta import relativedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import netsvc
logger = logging.getLogger('server')


class purchase_amendment(osv.osv):	
	
	_name = "purchase.amendment"	
	_order = "date desc"

	
	def _amount_line_tax(self, cr, uid, line, context=None):
		val = 0.0
		new_amt_to_per = line.discount_amend or 0.0 / line.product_qty_amend
		amt_to_per = (line.discount_amend or 0.0 / (line.product_qty_amend * line.price_unit_amend or 1.0 )) * 100
		discount_per = line.discount_per_amend
		tot_discount_per = amt_to_per + discount_per
		for c in self.pool.get('account.tax').compute_all(cr, uid, line.taxes_id_amend,
			line.price_unit_amend * (1-(tot_discount_per or 0.0)/100.0), line.product_qty_amend, line.product_id,
			line.amendment_id.partner_id)['taxes']:
			#print "ccccccccccccccccccccccccccccccc===========>>>", c
			val += c.get('amount', 0.0)
			#print "valvalvalvalvalvalvalvalvalvalvalvalvalval =============>>", val
		return val
	
	def _amount_all(self, cr, uid, ids, field_name, arg, context=None):
		res = {}
		cur_obj=self.pool.get('res.currency')
		for order in self.browse(cr, uid, ids, context=context):
			print "order=========================>>>>", order
			res[order.id] = {
				'amount_untaxed': 0.0,
				'amount_tax': 0.0,
				'amount_total': 0.0,
				'discount' : 0.0,
				'other_charge': 0.0,
			}
			val = val1 = val3 = 0.0
			cur = order.pricelist_id.currency_id
			for line in order.amendment_line:
				tot_discount = line.discount_amend + line.discount_per_value_amend
				val1 += line.price_subtotal
				val += self._amount_line_tax(cr, uid, line, context=context)
				val3 += tot_discount
			po_charges=order.value1_amend + order.value2_amend
			print "po_charges :::", po_charges , "val ::::", val, "val1::::", val1, "val3:::::", val3
			#res[order.id]['other_charge']=cur_obj.round(cr, uid, cur, po_charges)
			res[order.id]['amount_tax']=cur_obj.round(cr, uid, cur, val)
			res[order.id]['amount_untaxed']=cur_obj.round(cr, uid, cur, val1)
			res[order.id]['amount_total']=res[order.id]['amount_untaxed'] + res[order.id]['amount_tax'] + res[order.id]['other_charge']
			res[order.id]['discount']=cur_obj.round(cr, uid, cur, val3)
			self.write(cr, uid,order.id, {'other_charge' : po_charges})
		print "res ^^^^^^^^^^^^^,", "amount_total====", res[order.id]['amount_total'], "^^^^^^^^^^^^^^", res
		return res
		
	def _get_order(self, cr, uid, ids, context=None):
		result = {}
		for line in self.pool.get('purchase.amendment.line').browse(cr, uid, ids, context=context):
			print "line :::::::::::::::::::::::ids:::",ids, line
			result[line.amendment_id.id] = True
		return result.keys()
	
	_columns = {
		
		
		'name': fields.char('Amendment NO', size=128, readonly=True),
		'date':fields.date('Amendment Date',readonly=True),
		'po_id':fields.many2one('purchase.order','PO.NO', required=True,
			domain="[('state','=','approved') ,'&',('order_line.line_state','!=','cancel'),'&',('order_line.pending_qty','>','0')]",
			readonly=True,states={'draft':[('readonly',False)]}),
		'po_date':fields.date('PO Date', readonly=True),
		'partner_id':fields.many2one('res.partner', 'Supplier', readonly=True),
		'pricelist_id':fields.many2one('product.pricelist', 'Pricelist', required=True, states={'confirmed':[('readonly',True)], 'approved':[('readonly',True)]}),
		'currency_id': fields.related('pricelist_id', 'currency_id', type="many2one", relation="res.currency", string="Currency",readonly=True, required=True),
		'po_expenses_type1': fields.selection([('freight','Freight Charges'),('others','Others')], 'Expenses Type1',readonly=True),
		'po_expenses_type2': fields.selection([('freight','Freight Charges'),('others','Others')], 'Expenses Type2',readonly=True),
		'value1':fields.float('Value1', readonly=True),
		'value2':fields.float('Value2', readonly=True),
		'bill_type': fields.selection([('cash','Cash Bill'),('credit','Credit Bill')], 'Bill Type', readonly=True),
		'payment_mode': fields.selection([('ap','Advance Paid'),('on_receipt', 'On receipt of Goods and acceptance')],
			'Mode of Payment', readonly=True),
		'delivery_type':fields.many2one('deliverytype.master', 'Delivery Schedule', readonly=True),
		'delivery_mode': fields.selection([('direct','Direct'),('door','DOOR DELIVERY')], 'Mode of delivery', readonly=True),
		'note': fields.text('Remarks'),
		'active': fields.boolean('Active'),
		'amend_flag':fields.boolean('Amend Flag'),
		'state':fields.selection([('draft', 'Draft'),('amend', 'Processing'),('confirm', 'Confirmed'),('cancel','Cancel')], 'Status'),
		'amendment_line':fields.one2many('purchase.amendment.line', 'amendment_id', 'Amendment Line',
			states={'confirm':[('readonly', True)]}),
				
		'other_charge': fields.float('Other Charges(+)',readonly=True),
		'discount': fields.function(_amount_all, digits_compute= dp.get_precision('Account'), string='Total Discount(-)',
			store={
				'purchase.amendment': (lambda self, cr, uid, ids, c={}: ids, ['amendment_line'], 10),
				'purchase.amendment.line': (_get_order, ['price_unit_amend', 'tax_id', 'discount_amend', 'product_qty_amend'], 10),
			}, multi="sums", help="The amount without tax", track_visibility='always'),
		'amount_untaxed': fields.function(_amount_all, digits_compute= dp.get_precision('Account'), string='Untaxed Amount',
			store={
				'purchase.amendment': (lambda self, cr, uid, ids, c={}: ids, ['amendment_line'], 10),
				'purchase.amendment.line': (_get_order, ['price_unit_amend', 'tax_id', 'discount_amend', 'product_qty_amend'], 10),
			}, multi="sums", help="The amount without tax", track_visibility='always'),
		'amount_tax': fields.function(_amount_all, digits_compute= dp.get_precision('Account'), string='Taxes',
			store={
				'purchase.amendment': (lambda self, cr, uid, ids, c={}: ids, ['amendment_line'], 10),
				'purchase.amendment.line': (_get_order, ['price_unit_amend', 'tax_id', 'discount_amend', 'product_qty_amend'], 10),
			}, multi="sums", help="The tax amount"),
		'amount_total': fields.function(_amount_all, digits_compute= dp.get_precision('Account'), string='Total',
			store={
				'purchase.amendment': (lambda self, cr, uid, ids, c={}: ids, ['amendment_line'], 10),
				'purchase.amendment.line': (_get_order, ['price_unit_amend', 'tax_id', 'discount_amend', 'product_qty_amend'], 10),
				
			}, multi="sums",help="The total amount"),
		'grn_flag': fields.boolean('GRN'),
			
		# Amendment Fields:
		'partner_id_amend':fields.many2one('res.partner', 'Supplier'),
		'bill_type_amend': fields.selection([('cash','Cash Bill'),('credit','Credit Bill')], 'Amend Bill Type', 
			states={'confirm':[('readonly', True)]}),
		'payment_mode_amend': fields.selection([('ap','Advance Paid'),('on_receipt', 'On receipt of Goods and acceptance')],
			'Amend Mode of Payment', states={'confirm':[('readonly', True)]}),
		'delivery_type_amend':fields.many2one('deliverytype.master', 'Amend Delivery Schedule',
					states={'confirm':[('readonly', True)]}),
		'delivery_mode_amend': fields.selection([('direct','Direct'),('door','DOOR DELIVERY')], 'Amend Mode of delivery',
			states={'confirm':[('readonly', True)]}),
		'po_expenses_type1_amend': fields.selection([('freight','Freight Charges'),('others','Others')], 'Amend Expenses Type1',
			states={'confirm':[('readonly', True)]}),
		'po_expenses_type2_amend': fields.selection([('freight','Freight Charges'),('others','Others')], 'Amend Expenses Type2',
			states={'confirm':[('readonly', True)]}),
		'value1_amend':fields.float('Amend Value1', states={'confirm':[('readonly', True)]}),
		'value2_amend':fields.float('Amend Value2', states={'confirm':[('readonly', True)]}),
		'remark': fields.text('Remarks', states={'confirm':[('readonly', True)]}),
		'terms': fields.text('Terms & Conditions', states={'confirm':[('readonly', True)]}),
		
	}
	
	_defaults = {
	
	'date': fields.date.context_today,
	'state': 'draft',
	'active' : True,
	'name' : '/',
	}
	
	
	def onchange_poid(self, cr, uid, ids,po_id, pricelist_id):
		print "onchange_poid called***************************", ids
		po_obj = self.pool.get('purchase.order')
		value = {'pricelist_id': ''}
		if po_id:
			po_record = po_obj.browse(cr,uid,po_id)
			price_id = po_record.pricelist_id.id
			print "price_id==========>>", price_id
			value = {'pricelist_id': price_id}
			return {'value':value}	
		else:
			print "No Change"
	
	def unlink(self, cr, uid, ids, context=None):
		if context is None:
			context = {}
		amend = self.read(cr, uid, ids, ['state'], context=context)
		unlink_ids = []
		for t in amend:
			if t['state'] in ('draft'):
				unlink_ids.append(t['id'])
			else:
				raise osv.except_osv(_('Invalid action !'), _('System not allow to delete a UN-DRAFT state Purchase Amendment!!'))
		amend_lines_to_del = self.pool.get('purchase.amendment.line').search(cr, uid, [('amendment_id','in',unlink_ids)])
		self.pool.get('purchase.amendment.line').unlink(cr, uid, amend_lines_to_del)
		osv.osv.unlink(self, cr, uid, unlink_ids, context=context)
		return True
	
	def _prepare_amend_line(self, cr, uid, po_order, order_line, amend_id, context=None):
		print "po_order ::::::::>>>>>>>>>>>>>>>>>>>>", po_order, "===ID ====", po_order.id
		print "order_line ::::::::::::<<<<<<<<<<<<<<<", order_line

		return {
		
			'order_id':po_order.id,
			'product_id': order_line.product_id.id,
			'product_uom': order_line.product_uom.id,
			'product_qty': order_line.product_qty,
			'product_qty_amend' : order_line.product_qty,
			'pending_qty' : order_line.pending_qty,
			'pending_qty_amend' : order_line.pending_qty,
			'received_qty' : order_line.product_qty - order_line.pending_qty,
			'price_unit' : order_line.price_unit or 0.0,
			'price_unit_amend' : order_line.price_unit or 0.0,
			'discount' : order_line.discount,
			'discount_amend' : order_line.discount,
			'discount_per' : order_line.discount_per,
			'discount_per_amend' : order_line.discount_per,
			'discount_per_value' : order_line.discount_per_value,
			'discount_per_value_amend' : order_line.discount_per_value,
			'note' : order_line.name or '',
			'note_amend' : order_line.name or '',			
			'amendment_id': amend_id,
			'po_line_id': order_line.id,
			'line_bill':order_line.line_bill,
			
		}
	
	def make_amend(self,cr,uid,ids,amendment_id=False,context={}):
		
		po_id = False
		obj = self.browse(cr,uid,ids[0])
		print "Amend Obj ::::::::::",obj
		po_obj=self.pool.get('purchase.order')
		amend_obj=self.pool.get('purchase.amendment')
		amend_po_id = amend_obj.browse(cr,uid,obj.po_id.id)
		print "amend_po_id:::::::::", amend_po_id
		po_order = obj.po_id
		print "po_order :::::::::", po_order
		total_amends=amend_obj.search(cr,uid,[('po_id','=',obj.po_id.id)])
		print "total_amends ===================>>>", total_amends
		if po_order.picking_ids:
			grn = True
		else:
			grn = False			
		if len(total_amends) == 1:
			amend_no = po_order.name + '-01'
		else:
			amend_no = po_order.name + '-' + '%02d' % int(str(len(total_amends)))
        
		if obj.partner_id.id is False:
				
			self.pool.get('purchase.amendment').write(cr,uid,ids,
			{
			
			'amend_flag': True,
			'name' : amend_no, 
			'po_date': po_order.date_order,
			'partner_id': po_order.dest_address_id.id or po_order.partner_id.id,
			'partner_id_amend': po_order.dest_address_id.id or po_order.partner_id.id,
			'pricelist_id': po_order.pricelist_id.id,
			'currency_id': po_order.currency_id.id,
			'bill_type': po_order.bill_type,
			'bill_type_amend' : po_order.bill_type,
			'payment_mode' : po_order.payment_mode,
			'payment_mode_amend' : po_order.payment_mode,
			'delivery_type' : po_order.delivery_type.id,
			'delivery_type_amend' : po_order.delivery_type.id,
			'delivery_mode' : po_order.delivery_mode,
			'delivery_mode_amend' : po_order.delivery_mode,
			'po_expenses_type1' : po_order.po_expenses_type1,
			'po_expenses_type1_amend' : po_order.po_expenses_type1,
			'po_expenses_type2' : po_order.po_expenses_type2,
			'po_expenses_type2_amend' : po_order.po_expenses_type2,
			'value1' : po_order.value1,
			'value1_amend' : po_order.value1,
			'value2' : po_order.value2,
			'value2_amend' : po_order.value2,			
			'other_charge':po_order.other_charge,
			'grn_flag': grn,
			'remark':po_order.note,
			'terms':po_order.notes,
			'amendment_line' : [],
					
			#'amount_untaxed':po_order.amount_untaxed,
			#'amount_tax':po_order.amount_tax,
			#'amount_total':po_order.amount_total,
			#'discount':po_order.discount,

			
			})
			
			amend_id = obj.id
			todo_lines = []
			amend_line_obj = self.pool.get('purchase.amendment.line')
			wf_service = netsvc.LocalService("workflow")
			order_lines=po_order.order_line
			
			for order_line in order_lines:
				if order_line.line_state != 'cancel' and order_line.pending_qty > 0:
					amend_line = amend_line_obj.create(cr, uid, self._prepare_amend_line(cr, uid, po_order, order_line, amend_id,
									context=context))
					print "amend_line ==========================>>", amend_line
					cr.execute(""" select tax_id from purchase_order_taxe where ord_id = %s """  %(str(order_line.id)))
					data = cr.dictfetchall()
					val = [d['tax_id'] for d in data if 'tax_id' in d]
					print "val::::::::::::::::", val
					for i in range(len(val)):
						print "IIIIIIIIIIIIIIIIIIIII", val[i]
						cr.execute(""" INSERT INTO purchase_order_tax (amend_line_id,tax_id) VALUES(%s,%s) """ %(amend_line,val[i]))
						cr.execute(""" INSERT INTO amendment_order_tax (amend_line_id,tax_id) VALUES(%s,%s) """ %(amend_line,val[i]))
					todo_lines.append(amend_line_obj)
				else:
					print "NO Qty or Cancel"
				

			wf_service.trg_validate(uid, 'purchase.amendment', amend_id, 'button_confirm', cr)
			return [amend_id]
			cr.close()
		else:
			raise osv.except_osv(
				_('Amendment Created Already!'),
				_('System not allow to create Amendment again !!'))
		
	def confirm_amend(self,cr,uid,ids,context={}):
		
		amend_obj = self.browse(cr,uid,ids[0])
		po_obj = self.pool.get('purchase.order')
		product_obj = self.pool.get('product.product')
		po_line_obj = self.pool.get('purchase.order.line')
		amend_line_obj = self.pool.get('purchase.amendment.line')
		pi_line_obj = self.pool.get('purchase.requisition.line')
		stock_move_obj = self.pool.get('stock.move')
		po_id = False
		if amend_obj.amendment_line ==[]:
			raise osv.except_osv(
			_('Empty Purchase Amendment!'),
			_('System not allow to confirm a PO Amendment without Amendment Line !!'))
		#if amend_obj.po_id.bill_flag == True:
			#raise osv.except_osv(
			#_('System not allow for Amendment!'),
			#_('This Purchase Order has invoiced already..!!'))			
		else:			
			po_id = amend_obj.po_id.id
			po_record = po_obj.browse(cr,uid,po_id)
			po_obj.write(cr,uid,po_id,{'amend_flag': True})
			
			if amend_obj.partner_id.id != amend_obj.partner_id_amend.id:
				po_obj.write(cr,uid,po_id,{'partner_id': amend_obj.partner_id_amend.id})
				
			if amend_obj.bill_type != amend_obj.bill_type_amend:
				po_obj.write(cr,uid,po_id,{'bill_type': amend_obj.bill_type_amend})
				
			if amend_obj.payment_mode != amend_obj.payment_mode_amend:
				po_obj.write(cr,uid,po_id,{'payment_mode': amend_obj.payment_mode_amend})
				
			if amend_obj.delivery_type.id != amend_obj.delivery_type_amend.id:
				po_obj.write(cr,uid,po_id,{'delivery_type': amend_obj.delivery_type_amend.id})
				
			if amend_obj.delivery_mode != amend_obj.delivery_mode_amend:
				po_obj.write(cr,uid,po_id,{'delivery_mode': amend_obj.delivery_mode_amend})
				
			if amend_obj.po_expenses_type1 != amend_obj.po_expenses_type1_amend:
				po_obj.write(cr,uid,po_id,{'po_expenses_type1': amend_obj.po_expenses_type1_amend})
				
			if amend_obj.po_expenses_type2 != amend_obj.po_expenses_type2_amend:
				po_obj.write(cr,uid,po_id,{'po_expenses_type2': amend_obj.po_expenses_type2_amend})
				
			if amend_obj.value1 != amend_obj.value1_amend or amend_obj.value2 != amend_obj.value2_amend:
				tot_value = amend_obj.value1_amend + amend_obj.value2_amend
				po_obj.write(cr,uid,po_id,{
					'value1': amend_obj.value1_amend,
					'value2': amend_obj.value2_amend,
					'other_charge' : tot_value,
						})
			po_obj.write(cr,uid,po_id,{
					'notes':amend_obj.terms,
					'note':amend_obj.remark,
					})
			
		
		for amend_line in amend_obj.amendment_line:
			print "amend_line================>>", amend_line
			po_line_id = amend_line.po_line_id.id
			pol_record = amend_line.po_line_id
			diff_qty = amend_line.product_qty - amend_line.product_qty_amend
			print "diff_qty :::::::::::::::", diff_qty
			pending_diff_qty = amend_line.product_qty - amend_line.pending_qty
			print "pending_diff_qty :::::::::::", pending_diff_qty
			
			if amend_line.product_qty < amend_line.product_qty_amend:
				raise osv.except_osv(
				_('Amendment Qty Increase Error !'),
				_('You can not increase PO Qty'))
			
			if amend_line.line_state == 'cancel':
				if pol_record.pi_line_id:					
					pi_line_record = pi_line_obj.browse(cr, uid,pol_record.pi_line_id.id)
					pi_product_qty = pi_line_record.product_qty
					pi_pending_qty = pi_line_record.pending_qty
					print "pi_line_record ======================>>", pi_line_record
					print "pi_pending_qty ===================>>", pi_pending_qty
					print "**************************************"
					pi_product_qty += pol_record.product_qty
					pi_pending_qty += pol_record.pending_qty
					print "pi_pending_qty ===================>>", pi_pending_qty
					pi_line_obj.write(cr,uid,pol_record.pi_line_id.id,{'pending_qty' : pi_pending_qty})
					po_line_obj.write(cr,uid,po_line_id,{'line_state': amend_line.line_state,
														 'cancel_qty' :amend_line.cancel_qty,
														 'received_qty':amend_line.received_qty,
														  })
				else:
					po_line_obj.write(cr,uid,po_line_id,{'line_state': amend_line.line_state,
														 'cancel_qty' :amend_line.cancel_qty,
														 'received_qty':amend_line.received_qty,
														 })
				
			if amend_line.product_qty != amend_line.pending_qty:
				if diff_qty > pending_diff_qty:
					raise osv.except_osv(
					_('Few Quantities are Received!'),
					_('System can allow to Decrease upto %s Qty for Product --> %s !!')%(pending_diff_qty,amend_line.product_id.name))
					
			if amend_line.product_qty != amend_line.product_qty_amend:
				if amend_line.pending_qty == 0:
					raise osv.except_osv(
					_('All Qty has received for this PO !'),
					_('You can not increase PO Qty for product %s')%(amend_line.product_id.name))
					
				disc_value = (amend_line.product_qty_amend * amend_line.price_unit_amend) * amend_line.discount_per_amend / 100
				print "discount_per_value :::::::::::::::", disc_value
				po_line_obj.write(cr,uid,po_line_id,{
						'product_qty': amend_line.product_qty_amend,
						'pending_qty': amend_line.pending_qty_amend,
						'discount_per_value' : disc_value,
							})
					
			if amend_line.price_unit != amend_line.price_unit_amend:
				po_line_obj.write(cr,uid,po_line_id,{
					'price_unit': amend_line.price_unit_amend})
				self.grn_price_update(cr,uid,ids,amend_line)

				
			if amend_line.discount != amend_line.discount_amend:
				po_line_obj.write(cr,uid,po_line_id,{'discount': amend_line.discount_amend})
				self.grn_price_update(cr,uid,ids,amend_line)
				
			if amend_line.discount_per != amend_line.discount_per_amend:
				po_line_obj.write(cr,uid,po_line_id,{'discount_per': amend_line.discount_per_amend})
				
			if amend_line.discount_per_value != amend_line.discount_per_value_amend:
				po_line_obj.write(cr,uid,po_line_id,{'discount_per_value': amend_line.discount_per_value_amend})
			
			if amend_line.note != amend_line.note_amend:
				po_line_obj.write(cr,uid,po_line_id,{'name': amend_line.note_amend})
			
			print "amend_line.id::::::::::", amend_line.taxes_id
			print "amend_line.id:::taxes_id_amend:::::::", amend_line.taxes_id_amend
			
			cr.execute(""" select tax_id from amendment_order_tax where amend_line_id = %s """ %(amend_line.id))
			data = cr.dictfetchall()
			val = [d['tax_id'] for d in data if 'tax_id' in d]
			print "val::::::::::::::::", val
					
			cr.execute(""" delete from purchase_order_taxe where ord_id=%s """ %(po_line_id))
			self.grn_price_update(cr,uid,ids,amend_line)
			for i in range(len(val)):
				print "IIIIIIIIIIIIIIIIIIIII", val[i]
				cr.execute(""" INSERT INTO purchase_order_taxe (ord_id,tax_id) VALUES(%s,%s) """ %(po_line_id,val[i]))
					
				
			else:
				print "NO PO Line Changs"
			amend_line.write({'line_state': 'done'})
			
				
			
		print "Tax Calculation Methods are Going to Call"
		
		#po_line_obj._amount_line(cr,uid,[po_id],prop=None,arg=None,context=None)
		po_obj._amount_line_tax(cr,uid,pol_record,context=None)
		po_obj._amount_all(cr,uid,[po_id],field_name=None,arg=False,context=None)
		self.write(cr,uid,ids,{'state' : 'confirm'})
		
		return True
		cr.close()
		
	
	def grn_price_update(self,cr,uid,ids,amend_line, context={}):		
		amend = self.browse(cr, uid,ids[0])
		move_obj = self.pool.get('stock.move')
		lot_obj = self.pool.get('stock.production.lot')
		po_rec = amend.po_id
		if po_rec.picking_ids:
			for pick in po_rec.picking_ids:
				if pick.state != 'inv':					
					pick_id = pick.id
					move_id = move_obj.search(cr, uid, [( 'picking_id','=',pick_id)])
					for move in move_id:
						move_rec = move_obj.browse(cr, uid,move)						
						grn_price = amend_line.price_subtotal / amend_line.product_qty
						grn_price = round(grn_price, 2)
						
						grn_sql = """ update stock_move set price_unit=%s where move_type='in' and 
									id=%s and product_id=%s and move_type='in' """ %(grn_price,move_rec.id,amend_line.product_id.id)
						cr.execute(grn_sql)						
												
						if move_rec.product_uom.id == move_rec.stock_uom.id:
							new_price = amend_line.price_subtotal / amend_line.product_qty
							new_price = round(new_price, 2)
						else:							
							coff = amend_line.product_id.po_uom_coeff
							print "coff ================>>>", coff
							new_price = amend_line.price_subtotal / amend_line.product_qty
							new_price = new_price / coff
							new_price = round(new_price, 2)						
							
						print "new_price ------------------------->>>>>>>>> ------()(()))", new_price						
						lot_ids = lot_obj.search(cr, uid, [('grn_move','=',move)])
						sql = """ select grn_id,lot_id from out_grn_lines where lot_id=%s """%(lot_ids[0])
						cr.execute(sql)
						lot_data = cr.dictfetchall()						
						if lot_data:							
							out_id = [d['grn_id'] for d in lot_data if 'grn_id' in d]
							for i in out_id:								
								print "out_id +++++++++++++=================>>>>>", i
								out_rec = move_obj.browse(cr, uid,i)
								print "out_rec ()(())())()()()()()----------->>>",out_rec
								if out_rec.product_uom.id == amend_line.product_uom.id:																		
									issue_sql = """update stock_move set price_unit=%s where move_type='out' and id=%s
											 and product_id=%s """ %(grn_price,i,amend_line.product_id.id)
									cr.execute(issue_sql)									
								else:									
									issue_sql = """update stock_move set price_unit=%s where move_type='out' and id=%s
											 and product_id=%s """ %(new_price,i,amend_line.product_id.id)
									cr.execute(issue_sql)
								
								cons_sql = """update stock_move set price_unit=%s where move_type='cons' and src_id=%s
										 and product_id=%s """ %(new_price,i,amend_line.product_id.id)
								cr.execute(cons_sql)						
						
						lot_sql = """update stock_production_lot set price_unit=%s where grn_move=%s and 
									product_id=%s """ %(new_price,move_rec.id,amend_line.product_id.id)
						cr.execute(lot_sql)						
						
				else:
					print "All GRN has invoiced.........."
			return True
			cr.close()
	
purchase_amendment()


class purchase_amendment_line(osv.osv):
	
	
	_name = "purchase.amendment.line"
	
	def _amount_line(self, cr, uid, ids, prop, arg, context=None):
		cur_obj=self.pool.get('res.currency')
		tax_obj = self.pool.get('account.tax')
		res = {}
		if context is None:
			context = {}
		for line in self.browse(cr, uid, ids, context=context):
			amt_to_per = (line.discount_amend / (line.product_qty_amend * line.price_unit_amend or 1.0 )) * 100
			discount_per = line.discount_per_amend
			tot_discount_per = amt_to_per + discount_per
			price = line.price_unit_amend * (1 - (tot_discount_per or 0.0) / 100.0)
			taxes = tax_obj.compute_all(cr, uid, line.taxes_id_amend, price, line.product_qty, line.product_id, 
								line.amendment_id.partner_id)
			cur = line.amendment_id.pricelist_id.currency_id
			res[line.id] = cur_obj.round(cr, uid, cur, taxes['total_included'])
		return res
	
	_columns = {
	
	'price_subtotal': fields.function(_amount_line, string='Subtotal', digits_compute= dp.get_precision('Account')),
	'order_id': fields.many2one('purchase.order', 'Order ID'),
	'amendment_id':fields.many2one('purchase.amendment','Amendment', select=True, required=True, ondelete='cascade'),
	'product_id':fields.many2one('product.product', 'Product', required=True,readonly=True),
	'discount': fields.float('Discount Amount', digits_compute= dp.get_precision('Discount')),
	'price_unit': fields.float('Unit Price', digits_compute= dp.get_precision('Product Price')),
	'product_qty': fields.float('Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
	'pending_qty': fields.float('Pending Qty'),
	'po_qty':fields.float('PI Qty'),
	'received_qty':fields.float('Received Qty'),
	'cancel_qty':fields.float('Cancel Qty'),
	'product_uom': fields.many2one('product.uom', 'Product Unit of Measure',required=True,readonly=True),
	'note': fields.text('Remarks'),
	'discount_per': fields.float('Discount (%)', digits_compute= dp.get_precision('Discount')),
	'discount_per_value': fields.float('Discount(%)Value', digits_compute= dp.get_precision('Discount')),
	'po_line_id':fields.many2one('purchase.order.line', 'PO Line'),
	'taxes_id': fields.many2many('account.tax', 'purchase_order_tax', 'amend_line_id', 'tax_id','Taxes',readonly=True),
	'line_state': fields.selection([('draft', 'Draft'),('cancel', 'Cancel'),('done', 'Done')], 'Status'),
	'line_bill': fields.boolean('PO Bill'),
	# Amendment Fields:
	'discount_amend': fields.float('Amend Discount Amount', digits_compute= dp.get_precision('Discount')),
	'price_unit_amend': fields.float('Amend Price', digits_compute= dp.get_precision('Product Price')),
	'product_qty_amend': fields.float('Amend Quantity', digits_compute=dp.get_precision('Product Unit of Measure')),
	'pending_qty_amend': fields.float('Amend Pending Qty',line_state={'cancel':[('readonly', True)]}),
	'po_qty_amend':fields.float('Amend PI Qty'),
	'discount_per_amend': fields.float('Amend Discount (%)', digits_compute= dp.get_precision('Discount')),
	'discount_per_value_amend': fields.float('Amend Discount(%)Value', digits_compute= dp.get_precision('Discount')),
	'note_amend': fields.text('Amend Remarks'),
	'taxes_id_amend': fields.many2many('account.tax', 'amendment_order_tax', 'amend_line_id', 'tax_id','Amend Taxes'),
	'cancel_flag':fields.boolean('Flag'),

	}
	
	_defaults = {
	
		'line_state': 'draft',
		
		}
		
	def onchange_price_unit(self,cr,uid,price_unit,price_unit_amend,
					discount_per_amend,discount_per_value_amend,product_qty_amend):
						
		if price_unit != price_unit_amend:
			disc_value = (product_qty_amend * price_unit_amend) * discount_per_amend / 100
			return {'value': {'discount_per_value_amend': disc_value}}
		else:
			print "NO changes"
			
	
	def onchange_discount_value_calc(self, cr, uid, ids, discount_per_amend,product_qty_amend,price_unit_amend):
		print "Amend =======>onchange_discount_value_calc called"

		discount_value = (product_qty_amend * price_unit_amend) * discount_per_amend / 100
		print "discount_value::::::::::::", discount_value
		return {'value': {'discount_per_value_amend': discount_value}}
		
	def onchange_qty(self, cr, uid, ids,product_qty,product_qty_amend,pending_qty,pending_qty_amend):
		print "Amend =======>onchange_qty called"
	
		value = {'pending_qty_amend': ''}
		
		if product_qty == pending_qty:
			value = {'pending_qty_amend': product_qty_amend }			
		else:
			if product_qty != product_qty_amend:
				po_pen_qty = product_qty - pending_qty
				amend_pen_qty = product_qty_amend - po_pen_qty
				value = {'pending_qty_amend': amend_pen_qty}
			else:
				value = {'pending_qty_amend': pending_qty}
		return {'value': value}
		
	def pol_cancel(self, cr, uid, ids, context=None):

		line_rec = self.browse(cr,uid,ids)
		if line_rec[0].amendment_id.state == 'draft':			
			print "line_rec-------------------", line_rec
			print "line_rec[0].note_amend----------", line_rec[0].note_amend
			if line_rec[0].note_amend == '' or line_rec[0].note_amend == False:
				raise osv.except_osv(
					_('Remarks Required !! '),
					_('Without remarks you can not cancel a PO Item...'))				
			if line_rec[0].pending_qty == 0.0:
				raise osv.except_osv(
					_('All Quanties are Received !! '),
					_('You can cancel a PO line before receiving product'))					
			else:				
				self.write(cr,uid,ids,{'line_state':'cancel', 
										'cancel_flag': True,
										'cancel_qty' : line_rec[0].pending_qty,
										})
		else:
			raise osv.except_osv(
					_('Amendment Confirmed Already !! '),
					_('System allow to cancel a line Item in draft state only !!!...'))
						
		return True
		
	def pol_draft(self,cr,uid,ids,context=None):
		print "Amend =======>pol_draft called"
		self.write(cr,uid,ids,{'line_state':'draft', 'cancel_flag': False})
		return True
		
	"""	
	def unlink(self,cr,uid,ids,context=None):
		print "Amend =======>unlink called"
		if context is None:
			context = {}
			Allows to delete sales order lines in draft,cancel states
		for rec in self.browse(cr, uid, ids, context=context):
			if rec.line_state in ['draft', 'confirm']:
				raise osv.except_osv(_('Invalid Action!'), _('Cannot delete a sales order line which is in state \'%s\'.') %(rec.line_state,))
		return super(purchase_amendment_line, self).unlink(cr, uid, ids, context=context)	
		"""
	
	
purchase_amendment_line()

