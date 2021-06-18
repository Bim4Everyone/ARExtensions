# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
import clr
clr.AddReference('System')
clr.AddReference('System.Core')
clr.AddReference("System.Windows")
clr.AddReference("System.Windows.Forms")
# from System.Windows import Controls
from pyrevit.framework import Controls
from System.Windows.Forms import MessageBox
from System.Collections.Generic import List 
from Autodesk.Revit.DB import FilteredElementCollector, Transaction, TransactionGroup, BuiltInCategory, Level, SpatialElementBoundaryOptions, FamilyInstance, Phase,ViewSchedule,SectionType
from Autodesk.Revit.DB.Architecture import Room
import codecs
from pyrevit import forms, PYREVIT_APP_DIR
from pyrevit.forms import TemplateUserInputWindow, WarningBar
import collections

__doc__ = 'Удаляет из спецификации «КГ (Ключ.) - Наименование пом.» те наименования, которые не используются в проекте'

def GetPhaseId(phaseName, doc):
	collector = FilteredElementCollector(doc)
	collector.OfClass(Phase)
	phases = [phase for phase in collector if phase.Name.Equals(phaseName)]
	res = phases[0]
	return res

	
def error_print(errors, stopWork = True):
	print '|{:-^40}|'.format('')
	print '|{:-^40}|'.format('ВНИМАНИЕ')
	print '|{:-^40}|'.format('ОБНАРУЖЕНЫ ОШИБКИ')
	print '|{:-^40}|'.format('В СЛЕДУЮЩИХ ПОМЕЩЕНИЯХ')
	print '|{:-^40}|'.format('')
	for room in errors:
		print '|Помещение: '+room.base_name
		print '|Стадия: '+room.phase
		print '|Id: '+room.id
		print '|Корпус.Секция: '+room.section
		print '|Уровень: '+room.level
		print '|Имя подгруппы помещений: '+room.group
		print '| '
		print '|ОШИБКИ: '
		for error in room.exceptions:
			print '|'+error
		print '|{:-^40}|'.format('')
	if stopWork:
		raise SystemExit(1)

	
def error_finder_ver_2(rooms):
	'''
	Проверка на соответствие имени подгруппы и типа помещения
	Должно быть для подгрупп помещений, в имени которых есть АПАРТАМЕНТЫ или КВАРТИРА
	'''
	errors = []
	for section in rooms:
		for group in rooms[section]:
			temp_group = group.lower()
			
			if temp_group.find('апартаменты')>=0 or temp_group.find('квартира')>=0:
				
				flat = rooms[section][group]
				
				for room in flat:
				
					for sec_room in flat:
						if room.type != sec_room.type:
							room.ex +=1
							
				if flat[0].ex>0:
					flat.sort(key=lambda k: k.ex)
					check = False
					for idx,room in enumerate(flat):
						if check:
									#print 'Ну это вообще: '+room.stage+'_'+room.level+'_'+room.id
							room.append_exception('Несоответствие параметров "КГ_Имя подгруппы помещений" и "КГ_Тип помещения"')
							if room not in errors:
								errors.append(room)
						else:
							if flat[idx+1].ex > room.ex:
								check = True
	return errors

	
def error_name_print(names):
	print '|{:-^40}|'.format('')
	print '|{:-^40}|'.format('ВНИМАНИЕ')
	print '|{:-^40}|'.format('ДОБАВЬТЕ СЛЕДУЮЩИЕ НАИМЕНОВАНИЯ')
	print '|{:-^40}|'.format('В СПИСОК ПРИОРИТЕТОВ')
	print '|{:-^40}|'.format('')
	for name in names:
		print '|' + name
	print '|{:-^40}|'.format('')
	raise SystemExit(1)
	
class CSVTable:
	def __init__(self):
		self.isempty = True
		self.rows = []

		
class CSVObject:
	__separator = '____'
	def __init__(self, filePathm, file = None):
		self.__filePath = filePath
		self.__file = file
		self.readFile()
		
	def readFile(self):
		if file:
			f = self.__file
			f.seek(0)
			lines = f.readlines()
			
			self.__tables = {}
			tempTable = None
			for index, line in enumerate(lines):
				line = line.replace('\n', '')
				line = line.replace('\r', '')
				if self.__separator in line:
					tempTable = CSVTable()
					tableName = line.split(self.__separator)[1]
					self.__tables[tableName] = tempTable
				elif tempTable.isempty:
					tempTable.isempty = False
					tempTable.fields = line.split('|')
				else:
					tempRow = {}
					for index, value in enumerate(line.split('|')):
						tempRow[tempTable.fields[index]] = value
					tempTable.rows.append(tempRow)
		else:
			with codecs.open(self.__filePath,'a+',encoding='utf8') as f:
				f.seek(0)
				lines = f.readlines()
				
				self.__tables = {}
				tempTable = None
				for index, line in enumerate(lines):
					line = line.replace('\n', '')
					line = line.replace('\r', '')
					if self.__separator in line:
						tempTable = CSVTable()
						tableName = line.split(self.__separator)[1]
						self.__tables[tableName] = tempTable
					elif tempTable.isempty:
						tempTable.isempty = False
						tempTable.fields = line.split('|')
					else:
						tempRow = {}
						for index, value in enumerate(line.split('|')):
							tempRow[tempTable.fields[index]] = value
						tempTable.rows.append(tempRow)
					
	def get_table(self, tableName):
		if tableName not in self.__tables:
			self.__tables[tableName] = self.get_default_table(tableName)

		return self.__tables[tableName]
	
	def get_default_table(self, tableName):
		tempDict = {}
		with codecs.open(defaultFilePath,'r',encoding='utf8') as f:
			lines = f.readlines()
			for index, line in enumerate(lines):
				line = line.replace('\n', '')
				line = line.replace('\r', '')
				if self.__separator in line:
					tempTable = CSVTable()
					tempTableName = line.split(self.__separator)[1]
					tempDict[tempTableName] = tempTable
				elif tempTable.isempty:
					tempTable.isempty = False
					tempTable.fields = line.split('|')
				else:
					tempRow = {}
					for index, value in enumerate(line.split('|')):
						tempRow[tempTable.fields[index]] = value
					tempTable.rows.append(tempRow)
		return tempDict[tableName]
				
	
	def set_table(self, tableName, table):
		self.__tables[tableName] = table
	
	def writeFile(self):
		with codecs.open(self.__filePath,'w+',encoding='utf8') as f:
			for tableName in self.__tables:
				table = self.__tables[tableName]
				message = '{separator}{name}\n'.format(separator = self.__separator, name = tableName)
				f.write(message)
				message = '|'.join(table.fields)
				f.write(message)
				f.write('\n')
				for row in table.rows:
					strRow = row[table.fields[0]]
					for field in table.fields[1:]:
						strRow = '|'.join([strRow,row[field]])
					f.write(strRow)
					f.write('\n')
	
		
def GroupByParameter(lst, func):
	res = {}
	for el in lst:
		key = func(el)
		if key in res:
			res[key].append(el)
		else:
			res[key] = [el]
	return res

	
class CastRoom(object):
	__exceptions = []
	ex = 0
	
	def __init__(self, obj):
		self.__obj = obj
		
	def append_exception(self, ex):
		if ex not in self.__exceptions:
			self.__exceptions.append(ex)
	
	def get_parameter(self, name):
		return self.__obj.LookupParameter(name)

	def set_parameter(self, name, value):#Учесть без параметра
		try:
			return self.__obj.LookupParameter(name).Set(value)
		except Exception:
			print 'oh'
	
	@property
	def phase(self):
		return self.__obj.LookupParameter('Стадия').AsValueString()
	
	@property
	def base_name(self):
		name =  self.__obj.LookupParameter('Имя').AsString()
		if name:
			return name
		else:
			return '!БЕЗ ИМЕНИ!'
	
	@property
	def type(self):#Учесть без параметра
		type = self.__obj.LookupParameter('КГ_Тип помещения').AsValueString()
		if type:
			return type
		else:
			return ''
	
	@property
	def area(self):
		return self.__obj.LookupParameter("Площадь").AsDouble()
		
	@property
	def exceptions(self): 
		return self.__exceptions
				
	@property
	def level(self):
		return self.__obj.LookupParameter('Уровень').AsValueString()
		
	@property
	def name(self):#Учесть без параметра
		name = self.__obj.LookupParameter('КГ_Наименование').AsValueString()
		if name:
			return name
		else:
			return ''
	
	@property
	def section(self):
		section = self.__obj.LookupParameter('КГ_Корпус.Секция').AsValueString()
		if section:
			return section
		else:
			return ''
	
	@property
	def location(self):
		return self.__obj.Location
		
	@property
	def element_id(self):
		return self.__obj.Id
	
	@property
	def id(self):
		return self.__obj.Id.ToString()
	
	def get_boundary_segments(self, opt):
		return self.__obj.GetBoundarySegments(opt)
		
	@property
	def group(self):#Учесть без параметра
		group = self.__obj.LookupParameter('КГ_Имя подгруппы помещений').AsValueString()
		if group:
			return group
		else:
			return ''

			
class Option(object):
	def __init__(self, obj, state=False):
		self.state = state
		self.name = obj.Name
		self.elevation = obj.Elevation
		def __nonzero__(self):
			return self.state
		def __str__(self):
			return self.name

			
class Priority(object):
	def __init__(self, name, state=False):
		self.name = name
		self.state = state
		def __str__(self):
			return self.name

	
class SelectLevelFrom(forms.TemplateUserInputWindow):
	xaml_source = op.join(op.dirname(__file__),'MainWindow.xaml')
	
	def _setup(self, **kwargs):		

		h = 450
		w = 400
		self.Height = h
		self.MaxHeight = h
		self.MinHeight = h
		self.Width = w
		self.MaxWidth = w
		self.MinWidth = w
		self._verify_context()
		self._list_options()
		self.Title = "Удаление наименования помещений"
		
		self._numeric = True
	
	def _set_states(self, state=True, flip=False, selected=False):
		all_items = self.LevelList.ItemsSource
		if selected:
			current_list = self.LevelList.SelectedItems
		else:
			current_list = self.LevelList.ItemsSource
		for checkbox in current_list:
			if flip:
				checkbox.state = not checkbox.state
			else:
				checkbox.state = state

		# push list view to redraw
		self.LevelList.ItemsSource = None
		self.LevelList.ItemsSource = all_items
	
	def check_selected(self, sender, args):	
		"""Mark selected checkboxes as checked."""
		self._set_states(state=True, selected=True)

	def uncheck_selected(self, sender, args):	
		"""Mark selected checkboxes as unchecked."""
		self._set_states(state=False, selected=True)

	def suffix_txt_changed(self, sender, args ):
		pass
		
	def _verify_context(self):
		new_context = []
		for item in self._context:
			if not hasattr(item, 'state'):
				new_context.append(BaseCheckBoxItem(item))
			else:
				new_context.append(item)

		self._context = new_context
	
	def _list_options(self, checkbox_filter=None):
		self.LevelList.ItemsSource = self._context
	
	def Radio_1_Click(self, sender, args):
		self._numeric = False	
		
	def Radio_2_Click(self, sender, args):
		self._numeric = True
	
	def DelButton_Click(self, sender, args):
		#index = self.ParameterList.SelectedIndex
		list_2_delete = [x for x in self.LevelList.ItemsSource if x.state]
		all_items = self.LevelList.ItemsSource
		schedules  = [x for x in FilteredElementCollector(doc).OfClass(ViewSchedule).ToElements() if x.Name =='КГ (Ключ.) - Наименование пом.']
		el = schedules[0]

		table = el.GetTableData()
		section = table.GetSectionData(SectionType.Body)
		nRows = section.NumberOfRows

		# section.RemoveRow(index)
		#print(items[index].name)
		if nRows > 1:
			tg = TransactionGroup(doc, "Delete room that not used")
			tg.Start()
			t = Transaction(doc, "Update Sheet Parmeters")
			t.Start()
			for item in list_2_delete:
				#print(x)
				for  i in range(nRows-1):
					text = el.GetCellText(SectionType.Body,i+1, 0)
					
					if text == item.name:
						section.RemoveRow(i+1)		
			t.Commit()
			tg.Assimilate()
			
			for item_2_delete in list_2_delete:
				all_items.remove(item_2_delete)
			self.LevelList.ItemsSource = all_items
			self._verify_context()
			self._list_options()
			
	def DelAll_Click(self, sender, args):

		all_items = self.LevelList.ItemsSource
		schedules  = [x for x in FilteredElementCollector(doc).OfClass(ViewSchedule).ToElements() if x.Name =='КГ (Ключ.) - Наименование пом.']
		el = schedules[0]

		table = el.GetTableData()
		section = table.GetSectionData(SectionType.Body)
		nRows = section.NumberOfRows

		if nRows > 1:
			tg = TransactionGroup(doc, "Delete all rooms that not used")
			tg.Start()
			t = Transaction(doc, "Update Sheet Parmeters")
			t.Start()

			for item in all_items:
				#print(x)
				for  i in range(nRows-1):
					text = el.GetCellText(SectionType.Body,i+1, 0)
					
					if text == item.name:
						section.RemoveRow(i+1)	
			
			self.LevelList.ItemsSource = []
			self._verify_context()
			
			t.Commit()
			tg.Assimilate()
			

		

	
##########################################################################
#---------------------------------MAIN-----------------------------------#
##########################################################################
doc = __revit__.ActiveUIDocument.Document

uidoc = __revit__.ActiveUIDocument
view = __revit__.ActiveUIDocument.ActiveGraphicalView 


from Autodesk.Revit.DB import ParameterValueProvider, FilterNumericEquals, FilterIntegerRule, ElementParameterFilter, BuiltInCategory


rooms = [CastRoom(x) for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).ToElements()]
rooms_list = [x.name for x in rooms]

full_rooms_list = []
schedules  = [x for x in FilteredElementCollector(doc).OfClass(ViewSchedule).ToElements() if x.Name =='КГ (Ключ.) - Наименование пом.']
el = schedules[0]

table = el.GetTableData()
section = table.GetSectionData(SectionType.Body)
nRows = section.NumberOfRows
nColumns = section.NumberOfColumns

if nRows > 1:
	for  i in range(nRows-1):
		text = el.GetCellText(SectionType.Body,i+1, 0)
		full_rooms_list.append(text)

difference_list = [x for x in full_rooms_list if x not in rooms_list]
########################################################################## Priority(x)
#-------------------------Ввод параметров--------------------------------#
##########################################################################
names_ops = []
ops = [Priority(x) for x in difference_list]
res = SelectLevelFrom.show(ops, names=names_ops)
