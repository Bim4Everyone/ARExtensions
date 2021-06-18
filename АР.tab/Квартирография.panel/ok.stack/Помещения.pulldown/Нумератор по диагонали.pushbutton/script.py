# -*- coding: utf-8 -*- 
import clr
# from ctypes import *
# clr.AddReference("RevitLib.dll")
#from RevitLib import RevitLib
# mydll.RevitLib.Main()
# clr.AddReference('RevitLib.dll')
# clr.AddReference("RevitLib")
# from RevitLib import RevitLib
clr.AddReference("FormsCollector")
from FormsCollector import RenumerateVectorForm
clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox
from Autodesk.Revit.DB import Wall, ElementId, FilteredElementCollector, BuiltInCategory, Transaction, TransactionGroup
from Autodesk.Revit.DB.Architecture import Room
from System.Collections.Generic import List
from math import sqrt

from Autodesk.Revit.DB import ParameterValueProvider, FilterNumericEquals, FilterIntegerRule, ElementParameterFilter, BuiltInCategory

__doc__ = 'Нумерует помещения по заданному направлению'

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

selectionIds = uidoc.Selection.GetElementIds()
selection = [doc.GetElement(i) for i in selectionIds]
if len(selection) == 0:
	raise SystemExit(1)	

form = RenumerateVectorForm()
result = form.ShowDialog()
if not result:
	raise SystemExit(1)	
	
START = form.Result.Start
SUFFIX = form.Result.Suffix
PREFIX = form.Result.Prefix
DIRECTION = form.Result.Direction

class ImagineLine:
	def __init__(self, direction):
		self.x = direction.X
		self.y = -direction.Y
		
		
class GeometryRoom:
	line = ImagineLine(DIRECTION)
	
	def __init__(self, obj):
		self.x = obj.Location.Point.X
		self.y = obj.Location.Point.Y
		
		self.obj = obj
		
		self.range = self.x * self.line.x + self.y * self.line.y
		
	def set_num(self, num):
		self.obj.LookupParameter('Номер').Set(num)

# room = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).FirstElement()
# parameter = room.LookupParameter('Speech_Фиксация номера пом.') 
# pvp = ParameterValueProvider(parameter.Id) 
# fnrv = FilterNumericEquals() 
# fRule = FilterIntegerRule(pvp, fnrv, 1) 
# _filter = ElementParameterFilter(fRule, True) 

rooms = [GeometryRoom(x) for x in selection if isinstance(x, Room)]
if len(rooms) == 0:
	raise SystemExit(1)	
if rooms[0].obj.LookupParameter('Speech_Фиксация номера пом.'):
	rooms = [GeometryRoom(x) for x in selection if isinstance(x, Room) and x.LookupParameter('Speech_Фиксация номера пом.').AsInteger() == 0]
	placed_number = [x.LookupParameter('Номер').AsInteger() for x in selection if isinstance(x, Room) and x.LookupParameter('Speech_Фиксация номера пом.').AsInteger() == 1]
else:
	placed_number = []
rooms.sort(key=lambda k: k.range)

tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Calculating")
t.Start()
index = 0
for room in rooms:
	name = []
	

	if PREFIX:
		name.append(PREFIX)
	while index+START in placed_number:
		index += 1

	name.append(str(index+START))
	index += 1
	if SUFFIX:
		name.append(SUFFIX)

	
	room.set_num(''.join(name))
	
t.Commit()
tg.Assimilate()
#MessageBox.Show('Готово!')