# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
import clr
import math
import collections
from shutil import copyfile
from pyrevit import forms
from pyrevit.framework import Controls
clr.AddReference("System")
clr.AddReference("System.IO")
clr.AddReference("System.Windows.Forms")
clr.AddReference("ClassLibrary4")
from ClassLibrary4 import MainWindow
from System.IO import FileInfo
from System.Windows.Forms import MessageBox, SaveFileDialog, DialogResult
from System.Collections.Generic import List
from Autodesk.Revit.DB import DetailNurbSpline, CurveElement, ElementTransformUtils, \
                              DetailLine, View, ViewDuplicateOption, XYZ, LocationPoint, \
                              TransactionGroup, Transaction, FilteredElementCollector, \
                              ElementId, BuiltInCategory, FamilyInstance, ViewDuplicateOption, \
                              ViewSheet, FamilySymbol, Viewport, DetailEllipse, DetailArc, TextNote, \
                              ScheduleSheetInstance, ViewSchedule, SchedulableField, ScheduleFieldType, SectionType
from Autodesk.Revit.Creation import ItemFactoryBase
from Autodesk.Revit.UI.Selection import PickBoxStyle
from Autodesk.Revit.UI import RevitCommandId, PostableCommand

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application


__doc__ = 'Нумерует квартиры'

def GroupByParameter(lst, func):
	res = {}
	for el in lst:
		key = func(el)
		if key in res:
			res[key].append(el)
		else:
			res[key] = [el]
	return res


class Group:
	def __init__(self, rooms):
		self.rooms = rooms
		self.count = len(rooms)
		self.name = rooms[0].LookupParameter("КГ_Имя подгруппы помещений").AsValueString()
		self.number = 0
		splitedName = self.name.split(" ")
		if splitedName[-1].isdigit():
			self.name = " ".join(splitedName[:-1])
			self.number = int(splitedName[-1])

	def setNumber(self, number):
		if DISPLAY_TYPE:
			string_number = "{:0>3}".format(number)
		else:
			string_number = str(number)

		for room in self.rooms:
			room.LookupParameter("Speech_Номер квартиры").Set(string_number)


class Level:
	def __init__(self, rooms):

		groups_by_names = GroupByParameter(rooms, func = lambda x: x.LookupParameter("КГ_Имя подгруппы помещений").AsValueString())

		self.elevation = doc.GetElement(rooms[0].LookupParameter("Уровень").AsElementId()).Elevation
		self.groups = [Group(groups_by_names[group]) for group in groups_by_names]
		self.groups.sort(key=lambda x: (x.name, x.number))

	def numerateLevel(self, startNumber):
		number = startNumber

		for group in self.groups:
			group.setNumber(number)
			number += 1

		return number


class Section:
	def __init__(self, rooms):
		levels_by_names = GroupByParameter(rooms, func = lambda x: x.LookupParameter("Уровень").AsValueString())
		
		self.name = rooms[0].LookupParameter("КГ_Корпус.Секция").AsValueString()
		self.levels = [Level(levels_by_names[level]) for level in levels_by_names]
		self.levels.sort(key=lambda x: x.elevation)
	
	def numerateSection(self, startNumber):
		number = startNumber

		for level in self.levels:
			number = level.numerateLevel(number)
		
		return number







##########################################################################
#----------------------------------MAIN----------------------------------#
##########################################################################
elements = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).ToElements()
elements1 = []
for x in GroupByParameter(elements, func = lambda x: x.LookupParameter("КГ_Тип нумерации подгрупп").AsString()):
	intX = int(x)
	if intX <> None:
		elements1.append(intX)
elements1.sort()
elements2 = [int(x) for x in GroupByParameter(elements, func = lambda x: x.LookupParameter("КГ_Номера квартир в Секции").AsInteger())]
elements2.sort()
window = MainWindow()
window.SetNumbers(List[int](elements1), List[int](elements2))
res = window.ShowDialog()
if res:
	GROUP_NUM_TYPE = str(window.SelectedGroup)
	SECTION_NUM_TYPE = window.SelectedSection
	DISPLAY_TYPE = window.DisplayType

	elements = [x for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).ToElements() \
												if x.LookupParameter("КГ_Тип нумерации подгрупп").AsString() == GROUP_NUM_TYPE and \
												x.LookupParameter("КГ_Номера квартир в Секции").AsInteger() == SECTION_NUM_TYPE]

	rooms = GroupByParameter(elements, func = lambda x: x.LookupParameter("КГ_Корпус.Секция").AsValueString())

	sections = [Section(rooms[section]) for section in rooms]
	sections.sort(key=lambda x: x.name)

	startSectionNumber = 1

	tg = TransactionGroup(doc, "Update")
	tg.Start()
	t = Transaction(doc, "Calculating")
	t.Start()

	for section in sections:
		startSectionNumber = section.numerateSection(startSectionNumber)

	t.Commit()
	tg.Assimilate()

	MessageBox.Show('Готово!')
