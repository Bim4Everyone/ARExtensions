# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
import clr
clr.AddReference('System')
clr.AddReference('System.Windows.Forms')
from System.Windows.Forms import MessageBox
from System.Collections.Generic import List 
from Autodesk.Revit.DB import DisplayUnitType, UnitUtils, \
							IntersectionResultArray, SetComparisonResult, \
							CurveArray, SpatialElementBoundaryOptions, \
							Transform, Arc, Line, ViewDuplicateOption,\
							ViewType, View, FilteredElementCollector, \
							DimensionType, Transaction, TransactionGroup, \
							ElementId, BuiltInCategory, Grid, \
							InstanceVoidCutUtils, FamilySymbol, \
							FamilyInstanceFilter, Wall, XYZ, WallType
from Autodesk.Revit.DB.Architecture import Room
from Autodesk.Revit.Creation import ItemFactoryBase
import Autodesk
from System.Windows.Forms import MessageBox
from pyrevit import revit, script
from pyrevit import DB
from math import sqrt, acos, asin, sin
__title__ = 'Проверка помещений на ошибки'


__doc__ = 'Проверяет все помещения в проекте на ошибки контуров помещений'

class ContourExtractor:
	def __init__(self, room):
		self.__object = room

	def getContours(self):
		opt = SpatialElementBoundaryOptions()
		segs = self.__object.GetBoundarySegments(opt)
		boundarySegmentsList = segs
		contours = []
		for boundarySegments in boundarySegmentsList:
			contours.append(self.__getContourFromBoundarySegments(boundarySegments))
		return contours

	def __getContourFromBoundarySegments(self, boundarySegments):
		contour = []
		for boundarySegment in boundarySegments:
			curve = boundarySegment.GetCurve()
			contour.append(curve)
		return contour


class RoomContour:
	def __init__(self, room):
		contours = ContourExtractor(room).getContours()
		self.mainContour = contours[0]
		self.subContours = contours[1:]
		self.location = room.Location.Point
		self.id = room.Id
		self.floor = None


class ContourIntersectionFinder:
	message = 'Помещение имеет самопересекающийся контур'

	@staticmethod
	def find(contour):
		intersectionResultArray = clr.Reference[IntersectionResultArray]()
		length = len(contour)
		for i in range(length-2):
			curve = contour[i]
			for j in range(i+2, length):
				if i == 0 and j == length-1:
					continue

				secondCurve = contour[j]
				intersect = curve.Intersect(secondCurve, intersectionResultArray)

				if intersect == SetComparisonResult.Overlap:
					return True
		return False

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application
view = __revit__.ActiveUIDocument.ActiveGraphicalView 
view = doc.ActiveView

output = script.get_output()
selection = [ doc.GetElement( elId ) for elId in __revit__.ActiveUIDocument.Selection.GetElementIds() ]
roomSelection = [x for x in selection if isinstance(x, Room)]
roomSelection = [x for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).ToElements() if x.LookupParameter("Площадь").AsDouble()>0]
roomContours = [RoomContour(x) for x in roomSelection]


room_ids = []
for room_contour in roomContours:
	if ContourIntersectionFinder.find(room_contour.mainContour):
		room_ids.append(room_contour.id)


if room_ids:
	print ContourIntersectionFinder.message
	for room_id in room_ids:
		try:
			print output.linkify(room_id)
		except Exception as e:
			print room_id
else:
	print 'Все ок!'

