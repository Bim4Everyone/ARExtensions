# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
from datetime import date

__doc__ = 'Не использовать данный нумератор!'

import clr
clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox

from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, BuiltInParameter, SpatialElementBoundaryOptions, Transaction, TransactionGroup, Level, FamilyInstance, Phase

from pyrevit import forms
from pyrevit.forms import TemplateUserInputWindow, WarningBar
from pyrevit.framework import Controls

from enum import Enum


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
			self.response = [x for x in self._context if x.state]
		else:
			self.response = self._context
		self.response = {'level':self.response}
		self.Close()

def error_print(errors):
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
	raise SystemExit(1)

def error_field_print(errors):
	print '|{:-^40}|'.format('')
	print '|{:-^40}|'.format('ВНИМАНИЕ')
	print '|{:-^40}|'.format('ОБНАРУЖЕНЫ ОШИБКИ')
	print '|{:-^40}|'.format('В СПЕЦИФИКАЦИЯХ')
	print '|{:-^40}|'.format('')
	for table in errors:
		if len(errors[table])>0:
			print '|В таблице: {}'.format(table)
			for field in errors[table]:
				print '|Неверно заполнен параметр: {}'.format(field)
			print '|{:-^40}|'.format('')
	raise SystemExit(1)

def error_table_print(errors):
	print '|{:-^40}|'.format('')
	print '|{:-^40}|'.format('ВНИМАНИЕ')
	print '|{:-^40}|'.format('НЕ ОБНАРУЖЕНЫ СПЕЦИФИКАЦИИИ')
	print '|{:-^40}|'.format('В СПЕЦИФИКАЦИЯХ')
	print '|{:-^40}|'.format('')
	for table in errors:
		if errors[table]:
			print '|{}'.format(table)
			print '|{:-^40}|'.format('')
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

def GroupByParameter(lst, func):
	res = {}
	for el in lst:
		key = func(el)
		if key in res:
			res[key].append(el)
		else:
			res[key] = [el]
	return res

def GetPhaseId(phaseName, doc):
	collector = FilteredElementCollector(doc)
	collector.OfClass(Phase)
	phases = [phase for phase in collector if phase.Name.Equals(phaseName)]
	res = phases[0]
	return res

class CastRoom(object):
	__exceptions = []
	ex = 0
	
	def __init__(self, obj):
		self.__obj = obj
		
	def append_exception(self, ex):
		if ex not in self.__exceptions:
			self.__exceptions.append(ex)
		
	@property
	def base_name(self):
		name =  self.__obj.LookupParameter('Имя').AsString()
		if name:
			return name
		else:
			return '!БЕЗ ИМЕНИ!'
	
	@property
	def exceptions(self): 
		return self.__exceptions
	
	@property
	def type(self):#Учесть без параметра
		type = self.__obj.LookupParameter('КГ_Тип помещения').AsValueString()
		if type:
			return type
		else:
			return ''
	
	@property
	def name(self):#Учесть без параметра
		name = self.__obj.LookupParameter('КГ_Наименование').AsValueString()
		if name:
			return name
		else:
			return ''
		
	@property
	def group(self):#Учесть без параметра
		group = self.__obj.LookupParameter('КГ_Имя подгруппы помещений').AsValueString()
		if group:
			return group
		else:
			return ''
		
	@property
	def section(self):#Учесть без параметра
		section = self.__obj.LookupParameter('КГ_Корпус.Секция').AsValueString()
		if section:
			return section
		else:
			return ''
		
	@property
	def level(self):
		return self.__obj.LookupParameter('Уровень').AsValueString()
	
	@property
	def id(self):
		return self.__obj.Id.ToString()
	
	@property
	def element_id(self):
		return self.__obj.Id
		
	@property
	def area(self):
		return self.__obj.LookupParameter("Площадь").AsDouble()
		
	@property
	def location(self):
		return self.__obj.Location
	
	@property
	def phase(self):
		return self.__obj.LookupParameter('Стадия').AsValueString()
	
	def get_boundary_segments(self, opt):
		return self.__obj.GetBoundarySegments(opt)

	def set_parameter(self, name, value):#Учесть без параметра
		try:
			return self.__obj.LookupParameter(name).Set(value)
		except Exception:
			pass
			
	def get_parameter(self, name):
		return self.__obj.LookupParameter(name)
			
	def set_parameters(self):
		if self.phase == 'Проект':
			section_short = self.get_parameter('КГ_Корпус.Секция короткое').AsString()
			self.set_parameter('Speech_Корпус.Секция короткое', section_short)

			group_short = self.get_parameter('КГ_Имя подгруппы пом. короткое').AsString()
			self.set_parameter('Speech_Имя подгруппы пом. короткое', group_short)
			
			try:
				type_short = self.get_parameter('КГ_Тип помещения короткий').AsString()
				self.set_parameter('Speech_Тип помещения', type_short)
			except Exception:
				pass
				
			try:
				fire_short = self.get_parameter('КГ_Пожарный отсек короткое').AsString()
				if fire_short:
					self.set_parameter('Speech_Пожарный отсек', fire_short)
			except Exception:
				pass
				
			level_short = self.level.replace(' этаж', '')
			self.set_parameter('Speech_Этаж', level_short)


##########################################################################
#---------------------------------MAIN-----------------------------------#
##########################################################################
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

LEVEL = []
errors = [] #Список ошибок

##########################################################################
#-------------------------Ввод параметров--------------------------------#
##########################################################################
lvls = FilteredElementCollector(doc).OfClass(Level)
ops = [Option(x) for x in lvls] 
ops.sort(key=lambda x: x.elevation)

res = SelectLevelFrom.show(ops,
				button_name='Рассчитать')

if res:
	LEVEL = [x.name for x in res['level']]
else:
	raise SystemExit(1)

from Autodesk.Revit.DB import ParameterValueProvider, FilterNumericEquals, FilterIntegerRule, ElementParameterFilter, BuiltInCategory

room = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).FirstElement()
parameter = room.LookupParameter('Speech_Фиксация номера пом.') 
pvp = ParameterValueProvider(parameter.Id) 
fnrv = FilterNumericEquals() 
fRule = FilterIntegerRule(pvp, fnrv, 1) 
_filter = ElementParameterFilter(fRule, True) 
_filter_inverted = ElementParameterFilter(fRule, False) 
rooms = [CastRoom(x) for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).WherePasses(_filter).ToElements()]
placed_numbers_collector = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).WherePasses(_filter_inverted).ToElements()
placed_numbers = {}
placed_numbers['1'] = [x.LookupParameter('Speech_Фиксация номера пом.').AsInteger() for x in placed_numbers_collector if x.LookupParameter("КГ_Тип нумерации помещений").AsString() == '1']
placed_numbers['2'] = [x.LookupParameter('Speech_Фиксация номера пом.').AsInteger() for x in placed_numbers_collector if x.LookupParameter("КГ_Тип нумерации помещений").AsString() == '2']

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
#-------------------Группировка по уровню--------------------------------#
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
		if (room.phase == 'Проект'):
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
#-------------------Оставляем проект			-------------------------#
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
	error_print(errors)
##########################################################################
#-------------------Группировка по квартирам и секциям-------------------#
##########################################################################
for level in LEVEL:
	rooms[level] = GroupByParameter(rooms[level], func = lambda x: x.section)
	for section in rooms[level]:
		rooms[level][section] = GroupByParameter(rooms[level][section], func = lambda x: x.group)
##########################################################################
#-------------------Проверка на имя подгруппы и тип помещения------------#
##########################################################################
for level in LEVEL:
	errors += error_finder_ver_2(rooms[level])
if errors:
	error_print(errors)

##########################################################################
#-------------------------Нумерация--------------------------------------#
##########################################################################
tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Calculating")
t.Start()

for level in LEVEL:
	for section in rooms[level]:
	
		section_counter = 1
		
		for group in rooms[level][section]:
		
			group_counter = 1
			
			for room in rooms[level][section][group]:
				num_type = room.get_parameter("КГ_Тип нумерации помещений").AsString()

				if num_type == '1':
					
					while section_counter in placed_numbers[num_type]:
						section_counter +=1

					room.set_parameter("Номер", str(section_counter))
					
					section_counter +=1
				
				elif num_type == '2':
					
					while group_counter in placed_numbers[num_type]:
						group_counter +=1
					
					room.set_parameter("Номер", str(group_counter))
					
					group_counter +=1

t.Commit()
tg.Assimilate()

MessageBox.Show('Готово!')