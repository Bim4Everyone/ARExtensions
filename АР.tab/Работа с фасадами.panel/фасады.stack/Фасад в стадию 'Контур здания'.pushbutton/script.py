# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
from datetime import date

import clr
clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox

from Autodesk.Revit.DB import WallSweep, FilteredElementCollector, BuiltInCategory, BuiltInParameter, SpatialElementBoundaryOptions, Transaction, TransactionGroup, Level, FamilyInstance, Phase, XYZ, Wall
from pyrevit import revit, DB, forms
from pyrevit.forms import TemplateUserInputWindow, WarningBar
from pyrevit.framework import Controls

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
view = __revit__.ActiveUIDocument.ActiveGraphicalView


class Option(object):
	def __init__(self, obj, state=False):
		self.state = state
		self.name = obj.Name
		self.elevation = obj.Elevation
		def __nonzero__(self):
			return self.state
		def __str__(self):
			return self.name

class SelectLevelFrom(forms.TemplateUserInputWindow):
	xaml_source = op.join(op.dirname(__file__),'SelectFromCheckboxes.xaml')
	
	def _setup(self, **kwargs):
		self.checked_only = kwargs.get('checked_only', True)
		button_name = kwargs.get('button_name', None)
		if button_name:
			self.select_b.Content = button_name
		
		self.list_lb.SelectionMode = Controls.SelectionMode.Extended
		
		self.Height = 550
		#for i in range(1,4):
		#	self.purpose.AddText(str(i))

		self._verify_context()
		self._list_options()

	def _verify_context(self):
		new_context = []
		for item in self._context:
			if not hasattr(item, 'state'):
				new_context.append(BaseCheckBoxItem(item))
			else:
				new_context.append(item)

		self._context = new_context

	def _list_options(self, checkbox_filter=None):
		if checkbox_filter:
			self.checkall_b.Content = 'Check'
			self.uncheckall_b.Content = 'Uncheck'
			self.toggleall_b.Content = 'Toggle'
			checkbox_filter = checkbox_filter.lower()
			self.list_lb.ItemsSource = \
				[checkbox for checkbox in self._context
				if checkbox_filter in checkbox.name.lower()]
		else:
			self.checkall_b.Content = 'Выделить все'
			self.uncheckall_b.Content = 'Сбросить выделение'
			self.toggleall_b.Content = 'Инвертировать'
			self.list_lb.ItemsSource = self._context

	def _set_states(self, state=True, flip=False, selected=False):
		all_items = self.list_lb.ItemsSource
		if selected:
			current_list = self.list_lb.SelectedItems
		else:
			current_list = self.list_lb.ItemsSource
		for checkbox in current_list:
			if flip:
				checkbox.state = not checkbox.state
			else:
				checkbox.state = state

		# push list view to redraw
		self.list_lb.ItemsSource = None
		self.list_lb.ItemsSource = all_items

	def toggle_all(self, sender, args):
		"""Handle toggle all button to toggle state of all check boxes."""
		self._set_states(flip=True)

	def check_all(self, sender, args):
		"""Handle check all button to mark all check boxes as checked."""
		self._set_states(state=True)

	def uncheck_all(self, sender, args):
		"""Handle uncheck all button to mark all check boxes as un-checked."""
		self._set_states(state=False)

	def check_selected(self, sender, args):
		"""Mark selected checkboxes as checked."""
		self._set_states(state=True, selected=True)

	def uncheck_selected(self, sender, args):
		"""Mark selected checkboxes as unchecked."""
		self._set_states(state=False, selected=True)

	def button_select(self, sender, args):
		"""Handle select button click."""
		if self.checked_only:
			self.response = [x.name for x in self._context if x.state]
		else:
			self.response = [x.name for x in self._context]
		self.response = {'level':self.response}
		self.Close()





selection = [doc.GetElement(x) for x in uidoc.Selection.GetElementIds()]
phases = [x for x in FilteredElementCollector(doc).OfClass(Phase)]
temp = FilteredElementCollector(doc).OfClass(FamilyInstance).ToElements()
wallsweeps = FilteredElementCollector(doc).OfClass(WallSweep).ToElements()

PHASE = None
LEVEL = []

		
lvls = FilteredElementCollector(doc).OfClass(Level)
ops = [Option(x) for x in lvls] 
ops.sort(key=lambda x: x.elevation)
res = SelectLevelFrom.show(ops,
				button_name='Рассчитать')

				
if res:
	LEVEL = [x for x in res['level']]

for phase in phases:
	if phase.Name == 'Контур здания':
		PHASE = phase
		break
	



wall = [x for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Walls).OfClass(Wall).ToElements()]
walls = []

for x in wall:
	level = x.LookupParameter('Базовая зависимость')
	if level:
		if level.AsValueString() in LEVEL:
			walls.append(x)
		

#print len(walls)
walls = [x for x in walls if x.Name.startswith("(Н)") and x.Name.find('Витраж')<0 and not x.LookupParameter('Семейство').AsValueString()=='Витраж']
wallIds = [x.Id for x in walls]
anotherWalls = [x for x in wall if x.Name.startswith("(Н)") and (x.Name.find('Витраж')>=0 or x.LookupParameter('Семейство').AsValueString()=='Витраж')]

tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Calculating")
t.Start()

associate = []

for wall in anotherWalls:
	try:
		wall.LookupParameter('Стадия возведения').Set(PHASE.Id)
	except:
		pass
		
for wall in walls:
	#print wall.Id
	try:
		wall.LookupParameter('Стадия возведения').Set(PHASE.Id)
	except:
		pass
	#print 'ok'

for te in temp:
	if te.Host:
		for wall in wallIds:
			if str(te.Host.Id) == wall.ToString():
				associate.append(te.Id)
				te.LookupParameter('Стадия возведения').Set(PHASE.Id)
				break
#print len(associate)	
'''
for ws in wallsweeps:
	for wall in wallIds:
		if wall.ToString() in ws.GetHostIds():
			associate.append(ws.Id)
			ws.LookupParameter('Стадия возведения').Set(PHASE.Id)
			break
'''
#selection = revit.get_selection()
#selection.set_to(associate)
#print len(associate)
t.Commit()
tg.Assimilate()