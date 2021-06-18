# -*- coding: utf-8 -*-
import os.path as op

__doc__ = 'Соединяет все внешние стены между собой'

import pickle

from operator import itemgetter
from System.Collections.Generic import List
from pyrevit import script
from pyrevit import revit, DB
from Autodesk.Revit.DB import JoinGeometryUtils
from pyrevit.coreutils import Timer
from math import sqrt

from pyrevit import forms
from pyrevit.forms import TemplateUserInputWindow, WarningBar
from pyrevit.framework import Controls


class SelectLevelFrom(forms.TemplateUserInputWindow):
	xaml_source = op.join(op.dirname(__file__),'SelectFromCheckboxes.xaml')
	
	def _setup(self, **kwargs):
		self.checked_only = kwargs.get('checked_only', True)
		button_name = kwargs.get('button_name', None)
		if button_name:
			self.select_b.Content = button_name

		self.Height = 120
		self.Width = 250
		#for i in range(1,4):
		#	self.purpose.AddText(str(i))



	def button_select(self, sender, args):
		"""Handle select button click."""
		self.response = {'jump': self.space_calc.IsChecked}
		self.Close()


		

		
class CasheWall:
	def __init__(self, wall):
		self.x = (wall.Location.Curve.GetEndPoint(0).X+wall.Location.Curve.GetEndPoint(1).X)/2
		self.y = (wall.Location.Curve.GetEndPoint(0).Y+wall.Location.Curve.GetEndPoint(1).Y)/2
		self.obj = wall
		lenghtX = wall.Location.Curve.GetEndPoint(0).X-wall.Location.Curve.GetEndPoint(1).X
		lenghtY = wall.Location.Curve.GetEndPoint(0).Y-wall.Location.Curve.GetEndPoint(1).Y
		self.lenght = sqrt(lenghtX**2+lenghtY**2)

def CheckWalls(firstWall, secondWall):
	res = (firstWall.x-secondWall.x)**2+(firstWall.x-secondWall.x)**2
	res = sqrt(res)
	if res <= (firstWall.lenght+secondWall.lenght)/2:
		return True
	else:
		return False		

timer=Timer()
__title__ = 'Соединить все внешние стены'
  
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

selection = uidoc.Selection.GetElementIds()


JUMP_FLAG = False


res = SelectLevelFrom.show([], button_name='Соединить')

if res:
	JUMP_FLAG = res['jump']
else:
	raise SystemExit(1)



wall = DB.FilteredElementCollector(doc).OfCategory( DB.BuiltInCategory.OST_Walls ).OfClass(DB.Wall).ToElements()
#wall = FilteredElementCollector(doc).WhereElementIsElementType().OfClass(Wall).ToElements()
#print dir(wall[0].Name)
walls = [x for x in wall if x.Name.startswith("(Н)") and x.Name.find('Витраж')<0 and not x.LookupParameter('Семейство').AsValueString()=='Витраж']
#uidoc.Selection.SetElementIds(List[DB.ElementId]([x.Id for x in walls]))

collectorFloors = {}
for wall in walls:
	key = wall.LookupParameter('Базовая зависимость')
	if key:
		key = key.AsValueString()
	else:
		continue
	if key in collectorFloors:
		collectorFloors[key].append(wall)
	else:
		collectorFloors[key] = [wall]

level  = DB.FilteredElementCollector(doc).OfCategory( DB.BuiltInCategory.OST_Levels ).OfClass(DB.Level).ToElements()
level = sorted([[x.Elevation, x] for x in level], key=itemgetter(0))
level = [x[1].Name for x in level]

for l in collectorFloors:
	for idx, wall in enumerate(collectorFloors[l]):
		collectorFloors[l][idx] = CasheWall(wall)
'''
tg = DB.TransactionGroup(doc, "Update")
tg.Start()
t = DB.Transaction(doc, "Update Sheet Parmeters")
t.Start()	

for floor in walls:
	for wall in walls:
		
		try:
			if JoinGeometryUtils.AreElementsJoined(doc,floor,wall):
				JoinGeometryUtils.UnjoinGeometry(doc,floor,wall)
		except Exception as ex:
			print ex
			#pass
		
t.Commit()	
tg.Assimilate()

'''
pairs = []
n = len(level)
ind = 0

for idx, l in enumerate(level):
	if l in collectorFloors:
		w = collectorFloors[l]
		for i, wall in enumerate(w):
			for secondWall in w[i+1:]:
				ind +=1
				if CheckWalls(wall, secondWall) and not JoinGeometryUtils.AreElementsJoined(doc,secondWall.obj,wall.obj):
					if {wall, secondWall} not in pairs:
						pairs.append({wall, secondWall})
				'''
				try:
					JoinGeometryUtils.JoinGeometry(doc,wall,secondWall)
				except Exception as ex:
					#print ex
					pass
				'''
		if idx < n-1:
			if level[idx+1] in collectorFloors:
				w2 = collectorFloors[level[idx+1]]
				for floor in w:
					for wall in w2:
						ind +=1
						if CheckWalls(wall, floor) and not JoinGeometryUtils.AreElementsJoined(doc,floor.obj,wall.obj):
							if {wall, floor} not in pairs:
								pairs.append({wall, floor})
						'''
						try:
							JoinGeometryUtils.JoinGeometry(doc,floor,wall)
						except Exception as ex:
							#print ex
							pass
						'''
		if idx < n-2 and JUMP_FLAG:
			if level[idx+2] in collectorFloors:
				w2 = collectorFloors[level[idx+2]]
				for floor in w:
					for wall in w2:
						ind +=1
						if CheckWalls(wall, floor) and not JoinGeometryUtils.AreElementsJoined(doc,floor.obj,wall.obj):
							if {wall, floor} not in pairs:
								pairs.append({wall, floor})
						'''
						try:
							JoinGeometryUtils.JoinGeometry(doc,floor,wall)
						except Exception as ex:
							#print ex
							pass
						'''


tg = DB.TransactionGroup(doc, "Update")
tg.Start()
t = DB.Transaction(doc, "Update Sheet Parmeters")
t.Start()

for pair in pairs:
	wall = pair.pop()
	secondWall = pair.pop()
	if not JoinGeometryUtils.AreElementsJoined(doc,wall.obj,secondWall.obj):
		try:
			JoinGeometryUtils.JoinGeometry(doc,wall.obj,secondWall.obj)
		except Exception as ex:
			#print ex
			pass
t.Commit()
tg.Assimilate()




