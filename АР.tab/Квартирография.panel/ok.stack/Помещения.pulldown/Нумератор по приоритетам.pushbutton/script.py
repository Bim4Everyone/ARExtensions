# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
import clr
import math	 

clr.AddReference('System')
clr.AddReference('System.Core')
clr.AddReference("System.Windows")
clr.AddReference("System.Windows.Forms")
# from System.Windows import Controls
from pyrevit.framework import Controls
from System.Windows.Forms import MessageBox
from System.Collections.Generic import List 
from Autodesk.Revit.DB import FilteredElementCollector, Transaction, TransactionGroup,\
								BuiltInCategory, Level, SpatialElementBoundaryOptions,\
								FamilyInstance, Phase,ViewSchedule,SectionType,\
								ScheduleFieldType
from Autodesk.Revit.DB.Architecture import Room
import codecs
from pyrevit import forms, PYREVIT_APP_DIR
from pyrevit.forms import TemplateUserInputWindow, WarningBar
import collections

__doc__ = 'Нумерует помещения в пределах подгрупп по заранее определенному порядку наименований помещений'

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
		#self.x = obj.Location.Point.X
		#self.y = obj.Location.Point.Y
		
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
		name =	self.__obj.LookupParameter('Имя').AsString()
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
	def location_x(self):
		return self.__obj.Location.Point.X
	@property
	def location_y(self):
		return self.__obj.Location.Point.Y
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
	def __init__(self, name):
		self.name = name
		def __str__(self):
			return self.name

	
class SelectLevelFrom(forms.TemplateUserInputWindow):
	xaml_source = op.join(op.dirname(__file__),'MainWindow.xaml')
	
	def _setup(self, **kwargs):		
		self.checked_only = kwargs.get('checked_only', True)
		button_name = kwargs.get('button_name', None)
		self.LevelList.SelectionMode = Controls.SelectionMode.Extended
		if button_name:
			self.select_b.Content = button_name
		
		names = kwargs.get('names', [])
		self.ParameterList.ItemsSource = names
		h = 620
		w = 510
		self.Height = h
		self.MaxHeight = h
		self.MinHeight = h
		self.Width = w
		self.MaxWidth = w
		self.MinWidth = w
		self._verify_context()
		self._list_options()
		
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
	
	def Add_All_Click(self, sender, args):
		parameterList = [x for x in self.ParameterList.ItemsSource]
		schedules  = [x for x in FilteredElementCollector(doc).OfClass(ViewSchedule).ToElements() if x.Name =='КГ (Ключ.) - Наименование пом.']
		el = schedules[0]

		table = el.GetTableData()
		section = table.GetSectionData(SectionType.Body)
		nRows = section.NumberOfRows
		nColumns = section.NumberOfColumns
		number_Col = 0
		for j in range(nColumns):
			data_Col = el.GetCellText(SectionType.Body,0, j)
			if data_Col == 'КГ_Наименование':
				number_Col = j
				break
		index = len(parameterList)
		if nRows > 1:
			for  i in range(nRows-1):
				text = el.GetCellText(SectionType.Body,i+1, number_Col)
				item_notinList = True
				for x in parameterList:
					if text == x.name:
						item_notinList = False
				if item_notinList:
					newListItem = Priority(text)
					parameterList.insert(index, newListItem)
					#self.ParameterList.ItemsSource = parameterList
					index = len(parameterList)
			self.ParameterList.ItemsSource = parameterList
			# for x in parameterList :
				# print(x.name) 
		
	def UpButton_Click(self, sender, args):
		items = [x for x in self.ParameterList.ItemsSource]
		index = self.ParameterList.SelectedIndex
		if index and index>=0:
			temp = items[index]
			items[index] = items[index-1]
			items[index-1] = temp
		self.ParameterList.ItemsSource = items
		
	def DownButton_Click(self, sender, args):
		items = [x for x in self.ParameterList.ItemsSource]
		index = self.ParameterList.SelectedIndex
		if index<(len(items)-1) and index>=0:
			temp = items[index]
			items[index] = items[index+1]
			items[index+1] = temp
		self.ParameterList.ItemsSource = items
		
	def DelButton_Click(self, sender, args):
		index = self.ParameterList.SelectedIndex
		if index >= 0:
			items = [x for x in self.ParameterList.ItemsSource]
			items.pop(index)
			self.ParameterList.ItemsSource = items
	
	def addField_Click(self, sender, args):
		text = self.NameField.Text
		if text:
			newListItem = Priority(text)
			parameterList = [x for x in self.ParameterList.ItemsSource]
			index = self.ParameterList.SelectedIndex
			index = index if index >= 0 else 0
			
			parameterList.insert(index, newListItem)
			self.ParameterList.ItemsSource = parameterList
	
	def Button_Click(self, sender, args):
		"""Handle select button click."""
		self.response = [x.name for x in self.LevelList.ItemsSource if x.state]
		
		priority = [x.name for x in self.ParameterList.ItemsSource]
		self.response = {'level':self.response,
						'priority':priority,
						'type':self._numeric,
						'selection':self.checkSelection.IsChecked,
						'suffix': self.suffix.Text,
						'prefix': self.prefix.Text}
		self.Close()
	
	def Save_Click(self, sender, args):
		"""Handle select button click."""
		self.response = [x.name for x in self.LevelList.ItemsSource if x.state]

		priority = [x.name for x in self.ParameterList.ItemsSource]
		self.response = {'level':[],
						'priority':priority,
						'type':self._numeric,
						'selection':self.checkSelection.IsChecked,
						'suffix': self.suffix.Text,
						'prefix': self.prefix.Text}
		self.Close()


##########################################################################
#---------------------------------MAIN-----------------------------------#
##########################################################################
doc = __revit__.ActiveUIDocument.Document

uidoc = __revit__.ActiveUIDocument
view = __revit__.ActiveUIDocument.ActiveGraphicalView 
#print '|{:-^40}|'.format('')
selection = [ doc.GetElement( elId ) for elId in __revit__.ActiveUIDocument.Selection.GetElementIds()]

priority_list = []
LEVEL = []
sorting_type =	True
errors = [] #Список ошибок
##########################################################################
#-------------------------Проверка файла проекта-------------------------#
##########################################################################
if not doc.IsWorkshared:
	MessageBox.Show('Открыт отсоединенный файл!')
	#raise SystemExit(1)

docTitle = doc.Title[:4]
if not (docTitle.isalpha() and docTitle.isupper()):
	MessageBox.Show('Ошибка в имени проекта!')
	#raise SystemExit(1)

docDigitTitle = doc.Title[4:6]
if docDigitTitle.isdigit():
	docTitle += docDigitTitle

fileName = docTitle
#fileName = 'avocado.csv'
filePathName = r'W:\BIM-Ресурсы\Revit - 5 Надстройки\1 - pySpeechLib\01 - Параметры проектов'
#filePath = op.join(op.dirname(__file__),fileName)
filePath = op.join(filePathName, fileName + '.csv')
#filePath = op.join(PYREVIT_APP_DIR, fileName + '.csv')
defaultFilePath = op.join(filePathName, '!Шаблон')



from Autodesk.Revit.DB import ParameterValueProvider, FilterNumericEquals, FilterIntegerRule, ElementParameterFilter, BuiltInCategory
room = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).FirstElement()
parameter = room.LookupParameter('Speech_Фиксация номера пом.') 
pvp = ParameterValueProvider(parameter.Id) 
fnrv = FilterNumericEquals() 
fRule = FilterIntegerRule(pvp, fnrv, 1) 
_filter = ElementParameterFilter(fRule, True) 
_filter_inverted = ElementParameterFilter(fRule, False) 
placed_numbers = [CastRoom(x) for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).WherePasses(_filter_inverted).ToElements()]
placed_numbers = GroupByParameter(placed_numbers, func = lambda x: x.level)

rooms = [CastRoom(x) for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).WherePasses(_filter).ToElements()]
##########################################################################
#-------------------------Получение данных с CSV-------------------------#
##########################################################################
f = codecs.open(filePath, 'a+', encoding='utf8')
import_tables = CSVObject(filePath, f)
n =	 import_tables.get_table('Нумерация помещений')
for row in n.rows:
	priority_list.append(row['Name'])
##########################################################################
#-------------------------Ввод параметров--------------------------------#
##########################################################################
lvls = [x for x in FilteredElementCollector(doc).OfClass(Level)]
lvls.sort(key=lambda x: x.Elevation)

LEVEL = [x.Name for x in lvls]

ops = [Option(x) for x in lvls]
#ops = []
names_ops = [Priority(x) for x in priority_list]
res = SelectLevelFrom.show(ops,
				button_name='Рассчитать', names=names_ops)
	
f.close()
if res:
	PREFIX = res['prefix']
	SUFFIX = res['suffix']
	priority_list = res['priority']
	sorting_type =	res['type']
	selection_check = res['selection']
	new_table = CSVTable()
	new_table.fields = ['id', 'Name']
	for id, name in enumerate(priority_list):
		new_table.rows.append({'id':str(id), 'Name': name})
	import_tables.set_table('Нумерация помещений', new_table)
	import_tables.writeFile()
	if not LEVEL and not selection_check:
		SystemExit(1)
		
	if selection_check:
		rooms = [CastRoom(x) for x in selection if isinstance(x, Room)]
	else:
		LEVEL = res['level']
else:
	raise SystemExit(1)


placed_numbers_errors = {}
for level in placed_numbers:
	placed_numbers[level] = GroupByParameter(placed_numbers[level], func = lambda x: x.section)
	for section in placed_numbers[level]:
		if sorting_type:
			placed_numbers[level][section] = GroupByParameter(placed_numbers[level][section], func = lambda x: x.group)
			for group in placed_numbers[level][section]:
				for inex, room in enumerate(placed_numbers[level][section][group]):
					try:
						placed_numbers[level][section][group][inex] = int(room.get_parameter('Номер').AsString())
					except Exception:
						error_location_name = '_'.join([level,section,group])
						if error_location_name in placed_numbers_errors:
							placed_numbers_errors[error_location_name].append(room)
						else:
							placed_numbers_errors[error_location_name] = [room]
		else:
			for inex, room in enumerate(placed_numbers[level][section]):
				try:
					placed_numbers[level][section][inex] = int(room.get_parameter('Номер').AsString())
				except Exception:
					error_location_name = '_'.join([level,section])
					if error_location_name in placed_numbers_errors:
						placed_numbers_errors[error_location_name].append(room)
					else:
						placed_numbers_errors[error_location_name] = [room]

##########################################################################
#-------------------Проверка неразмещенных-------------------------------#
##########################################################################
del_num = [] #Список неразмещенных помещений

for id,room in enumerate(rooms):
	if room.area>0:
		pass
	elif None == room.location:
		del_num.insert(0,id)

tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Update Sheet Parmeters")
t.Start()

for id in del_num:
	doc.Delete(rooms[id].element_id)
	del rooms[id]

t.Commit()
tg.Assimilate()
##########################################################################
#-------------------Группировка комнат-----------------------------------#
##########################################################################
rooms = GroupByParameter(rooms, func = lambda x: x.level)
for level in LEVEL:
	if level not in rooms:
		rooms[level] = []
##########################################################################
#-------------------Проверка избыточных и неокруженных-------------------#
##########################################################################
opt = SpatialElementBoundaryOptions()

for level in LEVEL:
	for room in rooms[level]:
		if room.area>0: 
			pass
		else:
			segs = room.get_boundary_segments(opt)
			if (None==segs) or (len(segs)==0):
				#print 'NotEnclosed'
				room.append_exception('Не окружено')
				if room not in errors:
					errors.append(room)
			else:
				room.append_exception('Избыточное')
				#print 'Redundant'
				if room not in errors:
					errors.append(room)
if errors:
	error_print(errors)
##########################################################################
#----------------------Проверка Параметров-------------------------------#
##########################################################################
for level in LEVEL:
	for room in rooms[level]:
		if room.name == '(нет)' or not room.name:
			room.append_exception('КГ_Наименование *не заполнено*')
			if room not in errors:
				errors.append(room)
		if (room.phase == 'Проект' or room.phase == 'Межквартирные перегородки'):
			if room.section == '(нет)' or not room.section:
				room.append_exception('КГ_Корпус.Секция *не заполнено*')
				if room not in errors:
					errors.append(room)
			if room.group == '(нет)' or not room.group:
				room.append_exception('КГ_Имя подгруппы помещений *не заполнено*')
				if room not in errors:
					errors.append(room)
if errors:
	error_print(errors)
##########################################################################
#-------------------Оставляем оставляем проект---------------------------#
##########################################################################
del_num = {} #Список неразмещенных помещений
ost_rooms ={}
for level in LEVEL:
	del_num[level] = []
	ost_rooms[level] = []
	for id,room in enumerate(rooms[level]):
		temp = [room.phase == 'Проект']
		if not any(temp):
			del_num[level].insert(0,id)
			ost_rooms[level].append(room)

for level in LEVEL:
	for id in del_num[level]:
		del rooms[level][id]
##########################################################################
#-------------------Проверка Корпус.Секция-------------------------------#
##########################################################################
'''
ДОБАВИТЬ ПРОВЕРКУ ЧЕРЕЗ ОКНА
'''
ops = [x.name for x in ops if x.elevation*0.3048*0.3048>=2]

doors = FilteredElementCollector(doc).OfClass(FamilyInstance).OfCategory(BuiltInCategory.OST_Doors).ToElements()
doors = [door for door in doors]
doors = GroupByParameter(doors, func = lambda x: x.LookupParameter('Уровень').AsValueString())
phase = GetPhaseId('Проект', doc)
for level in LEVEL:
	if level in ops:
		if not(level in doors) or len(rooms[level])<1:
			continue
		for door in doors[level]:
			try: 
				troom = door.ToRoom[phase]
				froom = door.FromRoom[phase]
				tloc = froom.LookupParameter('КГ_Корпус.Секция').AsValueString()
				floc = troom.LookupParameter('КГ_Корпус.Секция').AsValueString()
				if floc != tloc:
					troom = CastRoom(troom)
					froom = CastRoom(froom)
					troom.append_exception('Неверно задан параметр "КГ_Корпус.Секция"')
					#froom.append_exception('Неверно задан параметр "КГ_Корпус.Секция"')
					if troom not in errors:
						errors.append(troom)
					if froom not in errors:
						errors.append(froom)
			except Exception:
				pass
if errors:
	error_print(errors, stopWork=False)
	errors = []
##########################################################################
#-------------------Группировка по квартирам и секциям-------------------#
##########################################################################
sorting_dict = {}
for name in priority_list:
	sorting_dict[name] = []

for level in LEVEL:
	rooms[level] = GroupByParameter(rooms[level], func = lambda x: x.section)
	for section in rooms[level]:
		d = GroupByParameter(rooms[level][section], func = lambda x: x.group)
		rooms[level][section] = collections.OrderedDict(sorted(d.items()))


#Проверка недопустимых номеров
for level in LEVEL:
	for section in rooms[level]:
		if sorting_type:
			for group in rooms[level][section]:
				error_location_name = '_'.join([level,section,group])
				if error_location_name in placed_numbers_errors:
					print 'Помещения имеют непраивльный формат введенных данных в параметре "Номер"'
					for room in placed_numbers_errors[error_location_name]:
						print room.id
		else:
			error_location_name = '_'.join([level,section])
			if error_location_name in placed_numbers_errors:
				print 'Помещения имеют непраивльный формат введенных данных в параметре "Номер"'
				for room in placed_numbers_errors[error_location_name]:
					print room.id
##########################################################################
#-------------------Проверка на имя подгруппы и тип помещения------------#
##########################################################################
for level in LEVEL:
	errors += error_finder_ver_2(rooms[level])
if errors:
	error_print(errors)
##########################################################################
#-------------------Группировка по именам--------------------------------#
##########################################################################	
nonexisted_names = []
for level in LEVEL:
	for section in rooms[level]:
		for group in rooms[level][section]:
			#print '-{}-'.format(group)
			rooms[level][section][group] = GroupByParameter(rooms[level][section][group], func = lambda x: x.name)
			for name in rooms[level][section][group]:
				#print rooms[level][section][group][name]
				if name not in priority_list:
					nonexisted_names.append(name)
if nonexisted_names:
	response = set(nonexisted_names)
	error_name_print(response)
					
##########################################################################
#---------------------Нумерация комнат-----------------------------------#
##########################################################################
tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Calculating")
t.Start()
for level in LEVEL:
	level_numbers = placed_numbers[level] if level in placed_numbers else None
	
	for section in rooms[level]:
		section_numbers = None
		if level_numbers:
			section_numbers = level_numbers[section] if (section in level_numbers) and level_numbers else None



		number = 1
		for group in rooms[level][section]:
			if sorting_type:
				if section_numbers:
					group_numbers = section_numbers[group] if group in section_numbers else None
				else:
					group_numbers = None
					


			if sorting_type:
				number = 1
			group_names =  rooms[level][section][group]
			for name in priority_list:
				if name not in group_names:
					continue
				#print '{} {}'.format(room.location_x,room.location_y)
				sorted_names = sorted(group_names[name],key= lambda room:(math.sqrt((room.location_x)**2 + (room.location_y)**2)))
				#sorted_names = sorted(group_names[name],key= lambda room:(math.sqrt((room.x)**2 + (room.y)**2)))

				for room in sorted_names:
					#print '{} {} {}'.format(number,room.name, room.x)
					room_name = []
					if PREFIX:
						room_name.append(PREFIX)					
					if sorting_type:
						if group_numbers:
							while number in group_numbers:
								number += 1
					else:
						if section_numbers:
							while number in section_numbers:
								number += 1					
					room_name.append(str(number))
					if SUFFIX:
						room_name.append(SUFFIX)
					room.set_parameter('Номер',''.join(room_name))
					number += 1
t.Commit()
tg.Assimilate()

