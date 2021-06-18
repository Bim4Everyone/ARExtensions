# -*- coding: utf-8 -*-
import pickle

__doc__ = 'Разъединяет все соединенные внешние стены'
from operator import itemgetter
from System.Collections.Generic import List
from pyrevit import script
from pyrevit import revit, DB
from Autodesk.Revit.DB import JoinGeometryUtils
from pyrevit.coreutils import Timer
from pyrevit.forms import ProgressBar
timer=Timer()
__title__ = 'Отсоединить все внешние стены'
  
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

selection = uidoc.Selection.GetElementIds()

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

tg = DB.TransactionGroup(doc, "Update")
tg.Start()
t = DB.Transaction(doc, "Update Sheet Parmeters")
t.Start()	
max_value = len(walls)**2
with ProgressBar(cancellable=False, step=0) as pb:
	#pb.indeterminate = True
	pb.title = '{value}%'
	flag = 0
	counter = 0
	for floor in walls:
		for wall in walls:
			counter+=1
			flag+=1
			try:
				if JoinGeometryUtils.AreElementsJoined(doc,floor,wall):
					JoinGeometryUtils.UnjoinGeometry(doc,floor,wall)
					
			except Exception as ex:
				print ex
				#pass
			if flag >= max_value/100-1:
				percentCounter = float(counter)/max_value*100
				pb.update_progress(int(percentCounter),  100)
				flag = 0
		
t.Commit()	
tg.Assimilate()
'''
tg = DB.TransactionGroup(doc, "Update")
tg.Start()
t = DB.Transaction(doc, "Update Sheet Parmeters")
t.Start()
n = len(level)
ind = 0
for idx, l in enumerate(level):
	if l in collectorFloors:
		w = collectorFloors[l]
		for i, wall in enumerate(w):
			for secondWall in w[i+1:]:
				ind +=1
				try:
					JoinGeometryUtils.JoinGeometry(doc,wall,secondWall)
				except Exception as ex:
					#print ex
					pass
				
		if idx < n-1:
			if level[idx+1] in collectorFloors:
				w2 = collectorFloors[level[idx+1]]
				for floor in w:
					for wall in w2:
						ind +=1
						try:
							JoinGeometryUtils.JoinGeometry(doc,floor,wall)
						except Exception as ex:
							#print ex
							pass
		if idx < n-2:
			if level[idx+2] in collectorFloors:
				w2 = collectorFloors[level[idx+2]]
				for floor in w:
					for wall in w2:
						ind +=1
						try:
							JoinGeometryUtils.JoinGeometry(doc,floor,wall)
						except Exception as ex:
							#print ex
							pass


t.Commit()
tg.Assimilate()

'''