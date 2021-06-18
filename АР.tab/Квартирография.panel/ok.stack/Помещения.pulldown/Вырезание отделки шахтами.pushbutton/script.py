# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
import clr
clr.AddReference('System')
clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox
from System.Collections.Generic import List 
from Autodesk.Revit.DB import FilteredElementCollector, DimensionType, Transaction, TransactionGroup, ElementId, BuiltInCategory, Grid, InstanceVoidCutUtils, FamilySymbol, FamilyInstanceFilter, Wall, XYZ, WallType, Level, FamilyInstance
from Autodesk.Revit.Creation import ItemFactoryBase
clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox
from pyrevit import revit
from pyrevit import forms
from pyrevit.framework import Controls
from math import sqrt, acos, asin, sin

__doc__ = 'Вырезает отделочный слой стен семействами шахт'

__title__ = 'Вырезание отделки шахтами'


doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application
view = __revit__.ActiveUIDocument.ActiveGraphicalView 
view = doc.ActiveView

options = app.Create.NewGeometryOptions()

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
		self.response = {'level':self.response,
						'cut':self.RadioCut.IsChecked}
		self.Close()

'''
selections = [ elId for elId in __revit__.ActiveUIDocument.Selection.GetElementIds()]
selections = [doc.GetElement(x) for x in selections]
for wall in selections:
	wallTypeId = wall.GetTypeId()
	wallType = doc.GetElement(wallTypeId)
	if isinstance(wallType, WallType):
		structure = wallType.GetCompoundStructure()
		
		if structure is None:
			continue
			
		layers = structure.GetLayers()
		print len(layers)
'''
class BoundingGeometry():
	def __init__(self, obj):
		self.obj = obj
		
		self.transform = self.getTransform()
		self.name = obj.Name
		self.max = self.obj.get_BoundingBox(None).Max
		self.min = self.obj.get_BoundingBox(None).Min
		self.rectangleList = self.getTransformedPoints()
		
	def getTransform(self):
		return self.obj.GetTransform()
	
	
	def getTransformedPoints(self):
		transformX = self.transform.BasisX
		transformY = self.transform.BasisY
		res = []
		if (abs(transformX.X) < 1e-10) or (abs(transformX.Y) < 1e-10):
			newMin = self.min
			newMax = self.max
			res.append(newMin)
			res.append(XYZ(newMin.X, newMax.Y, self.min.Z))
			res.append(newMax)
			res.append(XYZ(newMax.X, newMin.Y, self.min.Z))
			
		else:
			newMinY = self.min.X*transformY.X + self.min.Y*transformY.Y
			newMinX = self.min.X*transformX.X + self.min.Y*transformX.Y
			
			newMaxX = self.max.X*transformX.X + self.max.Y*transformX.Y
			newMaxY = self.max.X*transformY.X + self.max.Y*transformY.Y
			
			newMin = XYZ(newMinX, newMinY, self.min.Z)
			newMax = XYZ(newMaxX, newMaxY, self.max.Z)
		
			res.append(newMin)
			res.append(XYZ(newMin.X, newMax.Y, self.min.Z))
			res.append(newMax)
			res.append(XYZ(newMax.X, newMin.Y, self.min.Z))
			
			for index, xyz in enumerate(res):
				x = xyz.X*transformX.X - xyz.Y*transformX.Y
				y = -xyz.X*transformY.X + xyz.Y*transformY.Y
				res[index] = XYZ(x, y, xyz.Z)
			
		return res
		
	@staticmethod
	def area(a, b, c):
		return (b.X - a.X) * (c.Y - a.Y) - (b.Y - a.Y) * (c.X - a.X)
		
	@staticmethod	
	def intersect_1(a, b, c, d):
		if (a > b):
			a,b = b,a
		if (c > d):
			c,d = d,c
		return max(a,c) <= min(b,d)
	
	
	def intersect(self, a, b, c, d): 
		return self.intersect_1 (a.X, b.X, c.X, d.X)\
			and self.intersect_1 (a.Y, b.Y, c.Y, d.Y)\
			and self.area(a,b,c) * self.area(a,b,d) <= 0\
			and self.area(c,d,a) * self.area(c,d,b) <= 0	
	
	
	
	def compare(self, wall):
		if ((wall.min.Z > self.min.Z) and (wall.min.Z < self.max.Z)) or\
			((wall.max.Z > self.min.Z) and (wall.max.Z < self.max.Z)) or\
			((wall.min.Z < self.min.Z) and (wall.max.Z > self.max.Z)):
			#print 'ok'
		
			for index, point in enumerate(self.rectangleList):
				for indexWall, pointWall in enumerate(wall.rectangleList):
					if self.intersect(self.rectangleList[index-1], point, wall.rectangleList[indexWall-1], pointWall):
						return True
		
		return False
		

class WallGeometry(BoundingGeometry):
	def __init__(self, obj):
		self.obj = obj
		
		self.transform = self.getTransform()
		self.name = obj.Name
		self.max = self.obj.get_BoundingBox(None).Max
		self.min = self.obj.get_BoundingBox(None).Min
		self.rectangleList = self.getTransformedPoints()
		
	def getTransform(self):
		return self.obj.Orientation
'''
tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Update Sheet Parmeters")
t.Start()

InstanceVoidCutUtils.AddInstanceVoidCut(doc,selections[1],selections[0])

t.Commit()
tg.Assimilate()
print InstanceVoidCutUtils.GetCuttingVoidInstances(selections[1])
'''

lvls = FilteredElementCollector(doc).OfClass(Level)
ops = [Option(x) for x in lvls] 
ops.sort(key=lambda x: x.elevation)

res = SelectLevelFrom.show(ops,
				button_name='Ок')
if res:
	if len(res['level'])<1:
		raise SystemExit(1)
else:
	raise SystemExit(1)

LEVEL = res['level']
CUT_MODE = res['cut']
res = []
shaftFamily = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_MechanicalEquipment).OfClass(FamilySymbol).ToElements()
for x in shaftFamily:
	name = x.LookupParameter('Имя типа').AsString()
	if 'Архитектурная' in name:
		res.append(x.Id)
	

instances = []
for f in res:
	instances += [BoundingGeometry(x) for x in FilteredElementCollector(doc).WherePasses(FamilyInstanceFilter(doc, f)).ToElements() if 'Шахта' in x.LookupParameter('Семейство').AsValueString()]
	
elevators = [BoundingGeometry(x) for x in FilteredElementCollector(doc).OfClass(FamilyInstance).ToElements() if 'Лифт и Шахта' in x.LookupParameter('Семейство').AsValueString()]
instances += elevators

#print len(instances) 
		
if CUT_MODE:
	walls = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Walls).OfClass(Wall).ToElements()
	walls = [x for x in walls if "(Н)" not in x.Name]
	fatWalls = []
	for wall in walls:
		level = wall.LookupParameter('Базовая зависимость')
		if not (level is None):
			level = level.AsValueString()
		else:
			pass
			#print wall.Id
		if level not in LEVEL:
			continue
		wallTypeId = wall.GetTypeId()
		wallType = doc.GetElement(wallTypeId)
		if isinstance(wallType, WallType):
			structure = wallType.GetCompoundStructure()
			
			if structure is None:
				continue
				
			layers = structure.GetLayers()
			if len(layers)>1:
				fatWalls.append(WallGeometry(wall))



				
	#print len(fatWalls)
	tg = TransactionGroup(doc, "Update")
	tg.Start()
	t = Transaction(doc, "Update Sheet Parmeters")
	t.Start()	
	for shaft in instances:
		for wall in fatWalls:
			if shaft.compare(wall):
				try:
					InstanceVoidCutUtils.AddInstanceVoidCut(doc,wall.obj,shaft.obj)
				except:
					pass

	t.Commit()
	tg.Assimilate()
else:
	tg = TransactionGroup(doc, "Update")
	tg.Start()
	t = Transaction(doc, "Update Sheet Parmeters")
	t.Start()
	for shaft in instances:
		for wallId in InstanceVoidCutUtils.GetElementsBeingCut(shaft.obj):
			wall = doc.GetElement(wallId)
			level = wall.LookupParameter('Базовая зависимость')
			if not (level is None):
				level = level.AsValueString()
			else:
				pass
				#print wallId
			if "(Н)" in wall.Name or level not in LEVEL:
				continue
			wallTypeId = wall.GetTypeId()
			wallType = doc.GetElement(wallTypeId)
			if isinstance(wallType, WallType):
				structure = wallType.GetCompoundStructure()
				if structure is None:
					continue
					
				layers = structure.GetLayers()
				if len(layers)>1:
					try:
						InstanceVoidCutUtils.RemoveInstanceVoidCut(doc,wall,shaft.obj)
					except:
						print 'pass'
	t.Commit()
	tg.Assimilate()
			
			
			
			
			
			
			
			
			
			
			
			