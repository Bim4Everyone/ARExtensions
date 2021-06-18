# -*- coding: utf-8 -*-
import os.path as op
import os
import sys

__doc__ = 'Выделяет все стены которые не соединены между собой'

from pyrevit import revit

from Autodesk.Revit.DB import Wall, GroupType, FilteredElementCollector, Location, Transaction, TransactionGroup, LocationCurve, ViewSchedule, StorageType, Phase,Reference, Options, XYZ, FamilyInstance 
from Autodesk.Revit.UI.Selection import ObjectType, ObjectSnapTypes
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

schedules  = [x for x in FilteredElementCollector(doc).OfClass(ViewSchedule).ToElements()]
#print schedules


'''
definition = vs.Definition
print vs.Name
print vs
for el in definition.GetSchedulableFields():

	ids = vs.Definition.GetFieldOrder()
	for id in ids:
		if (vs.Definition.GetField(id).GetSchedulableField() == el):
			#print el.GetName(doc)
			pass
		
typeCollector = FilteredElementCollector(vs.Document, vs.Id)
typeCollector.WhereElementIsElementType()
typeCollector = [x for x in typeCollector]
numberOfTypes = len(typeCollector)

instCollector = FilteredElementCollector(vs.Document, vs.Id)
instCollector.WhereElementIsNotElementType()
instCollector = [x for x in instCollector]

numberOfInstances = len(instCollector)

#print numberOfTypes
#print numberOfInstances
#print dir(instCollector[0])
for el in instCollector:
	for param in el.GetOrderedParameters():
		#print param.Definition.Name + ': '+ param.AsString()
		pass
	print '--'
	for param in el.GetOrderedParameters():
		print param.Definition.Name + ': '+ param.AsString()
	print '-----'
'''
	
class BaseSchedulable(object):
	__fields = {}


	def __init__(self, vs):
		instCollector = FilteredElementCollector(vs.Document, vs.Id)
		instCollector.WhereElementIsNotElementType()
		instCollector = [x for x in instCollector]
		
		self.get_fields(instCollector)
			
		for key in self.__fields:
			print key
			field = self.__fields[key]
			for elKey in field:
				el = field[elKey]
				if el.StorageType == StorageType.String:
					print el.AsString()
				elif el.StorageType == StorageType.Integer:
					print el.AsInteger()
				elif el.StorageType == StorageType.Double:
					print el.AsDouble()
				elif el.StorageType == StorageType.ElementId:
					print el.AsValueString()
				elif el.StorageType == StorageType.None:
					print el
					
			print '_____'
			
	def get_fields(self, lst):
		for el in lst:
			field = {}
			key = ''
			for param in el.GetOrderedParameters():
				if param.Definition.Name == 'Ключевое имя':
					key = param.AsString()
				else:
					field[param.Definition.Name] = param
			self.__fields[key] = field
		
		return 1
	
#BaseSchedulable(vs)

'''
selection = [ doc.GetElement( elId ) for elId in __revit__.ActiveUIDocument.Selection.GetElementIds() ]
vs = selection[0]

box = vs.get_BoundingBox(None)
print box
print dir(box)
print box.Max
print box.Min
print vs.Location.Rotation
print vs.Location.Point
print '-----'
for sel in selection:
	print sel.Location.Point
'''
r = uidoc.Selection.PickObject(ObjectType.PointOnElement, " Выберите точку на поверхности "+ "для вставки семейства.")
#print dir(r)
vs = doc.GetElement(r.ElementId)
p = r.GlobalPoint
if not isinstance(vs, Wall):
	raise SystemExit(1)
locCurve = vs.Location


curve = locCurve.Curve

p1 = curve.GetEndPoint(0)
p2 = curve.GetEndPoint(1)

class plane:

	def __init__(self, m1, m2, p, h):
		m1 = XYZ(m1.X, m1.Y, m1.Z)
		m2 = XYZ(m2.X, m2.Y, m2.Z)
		m3 = XYZ(m1.X, m1.Y, m1.Z+10)
		self.P = p
		self.height = h
		
		self.m1 = m1
		self.m2 = m2
		
		vec1 = XYZ(m2.X - m1.X, m2.Y - m1.Y, m2.Z - m1.Z)
		vec2 = XYZ(m3.X - m3.X, m3.Y - m1.Y, m3.Z - m1.Z)
		self.N = XYZ(vec1.Y*vec2.Z - vec2.Y*vec1.Z, vec1.Z*vec2.X - vec2.Z*vec1.X, vec1.X*vec2.Y - vec2.X*vec1.Y)
		#print self.N
	
	def is_instance(self, p):
		A = self.N.X
		B = self.N.Y
		C = self.N.Z
		x = self.P.X
		y = self.P.Y
		z = self.P.Z
		#print A*(x - p.X)+B*(y - p.Y)+C*(z - p.Z)
		if abs(A*(x - p.X)+B*(y - p.Y)+C*(z - p.Z)) < 0.0000001:
			if p.Z > self.m1.Z and p.Z <= (self.height + self.m1.Z+5/304.8):
				return True
			else:
				return False
		else:
			return False

h = vs.LookupParameter('Неприсоединенная высота').AsDouble()
pl = plane(p1, p2, p, h)

famInst = [x for x in FilteredElementCollector(doc).OfClass(FamilyInstance).ToElements() if x.Host is None and not isinstance(x.Location,LocationCurve)]
famInst = [x.Id for x in famInst if pl.is_instance(x.Location.Point)]
selection = revit.get_selection()
selection.set_to(famInst)