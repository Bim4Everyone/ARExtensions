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
clr.AddReference('System')
clr.AddReference('System.IO')
clr.AddReference("System.Windows.Forms")
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

__doc__ = 'Добавляет новые наименования помещений в спецификацию «КГ (Ключ.) - Наименование пом.»'

clr.AddReference('ClassLibrary3')
#from ClassLibrary3 import Student 

# #sys.path.append(r'C:\Users\a.ali\Downloads')
# #clr.AddReference(os.path.join(os.path.abspath('.'), 'dlls', 'RevitLib.dll')) clr.AddReferenceToFile("TwoCardPokerLib.dll")
# clr.AddReference('ClassLibrary2.dll')
# from ClassLibrary1 import Student 
# x = Student(5,"sdfasdf")
# print(x.returnMyWord())


doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = __revit__.Application

selection = [x for x in FilteredElementCollector(doc).OfClass(ViewSchedule).WhereElementIsNotElementType().ToElements() if '(Ключ.) - Наименование пом' in x.Name]
viewSchedule = selection[0]

listElements_before = [x for x in FilteredElementCollector(viewSchedule.Document, viewSchedule.Id).WhereElementIsNotElementType().ToElements()]
# for element in listElements_before:
    # name = element.LookupParameter('Ключевое имя').AsString()
    # name_dub = element.LookupParameter('Имя').AsString()

    # if name != name_dub:

        # MessageBox.Show('В спецификации есть неправильно заполненные поля!')

        # raise(SystemExit(1))

from ClassLibrary3 import MainWindow

def add_func():

	window = MainWindow()
	#window.Name.set('sdfsdf')
	res = window.ShowDialog()

	if not res:
		raise(SystemExit(1))

	res = window.Response
	name = res.Name
	#print(name)
	reductionFactor = res.ReductionFactor
	closing = res.Closing
	living = res.Living
	
	parameters_dict = {
		'Ключевое имя': name,
		'Имя': name,
		'Назначение': 'Жилье',
		'КГ_Понижающий коэффициент': reductionFactor,
		'КГ_Открытое_Закрытое': closing,
		'КГ_Жилое_Нежилое': living,
		'КГ_Коэф. расчёта площади': 1
	}


	selection = [x for x in FilteredElementCollector(doc).OfClass(ViewSchedule).WhereElementIsNotElementType().ToElements() if '(Ключ.) - Наименование пом' in x.Name]
	viewSchedule = selection[0]
	tableData = viewSchedule.GetTableData()
	tsd = tableData.GetSectionData(SectionType.Body)

	listNames_before = [x.LookupParameter('Ключевое имя').AsString() for x in FilteredElementCollector(viewSchedule.Document, viewSchedule.Id).WhereElementIsNotElementType().ToElements()]
	if name in listNames_before:
		MessageBox.Show('Данное наименование уже есть в спецификации!')
		add_func()
		#raise(SystemExit(1))
	else:
		list_before = [x.Id.IntegerValue for x in FilteredElementCollector(viewSchedule.Document, viewSchedule.Id).WhereElementIsNotElementType().ToElements()]


		tg = TransactionGroup(doc, "Update")
		tg.Start()
		t = Transaction(doc, "Calculating")
		t.Start()


		tsd.InsertRow(tsd.FirstRowNumber )


		list_after = [x for x in FilteredElementCollector(viewSchedule.Document, viewSchedule.Id).WhereElementIsNotElementType().ToElements() if x.Id.IntegerValue not in list_before]
		new_element = list_after[0]

		for parameter_name in parameters_dict:
			parameter = new_element.LookupParameter(parameter_name)
			if parameter:
				parameter.Set(parameters_dict[parameter_name])
				


		t.Commit()
		tg.Assimilate()

add_func()

