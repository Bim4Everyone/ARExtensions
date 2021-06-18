# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
from datetime import date

sys.path.append(op.dirname(__file__))
from shedulable import errCollector

import clr
clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox
__doc__ = '''Считает площадь квартир. Полная версия квартирографии.

Заполняет следующие параметры площадей помещений:
Speech_Площадь квартиры
Speech_Площадь квартиры попятну
Speech_Площадь квартиры с коэф.
Speech_Площадь квартиры жилая
Speech_Площадь квартиры фактическая

Speech_Площадь с коэффициентом
Speech_Площадь округлённая'''

from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory, BuiltInParameter, SpatialElementBoundaryOptions, Transaction, TransactionGroup, Level, FamilyInstance, Phase
from Autodesk.Revit.DB.Architecture import Room
from pyrevit import forms
from pyrevit.forms import TemplateUserInputWindow, WarningBar
from pyrevit.framework import Controls
from pySpeech.configkeeper import ConfigKeeper
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
		#for i in range(1,4):
		#	self.purpose.AddText(str(i))
		self.Title = "Квартирография Стадии П"

		self._verify_context()
		self._list_options()
		self._load_config()
	
	def _load_config(self):
		configKeeper = ConfigKeeper()

		if "space_calc_стадияП" in configKeeper:
			self.space_calc.IsChecked = configKeeper["space_calc_стадияП"]

		if "purpose_стадияП" in configKeeper:
			self.purpose.SelectedIndex  = configKeeper["purpose_стадияП"]

	def _update_config(self):
		configKeeper = ConfigKeeper()
		configKeeper["space_calc_стадияП"] = bool(self.space_calc.IsChecked)
		configKeeper["purpose_стадияП"] = int(self.purpose.SelectedIndex)
		configKeeper.update()


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
		self.response = {'level':self.response,
						'space':self.space_calc.IsChecked,
						'eps':int(self.purpose.Text),
						'selection':self.checkSelection.IsChecked}
		self._update_config()
		self.Close()


def error_print(errors, stopWork):
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
			print '|КГ (Ключ.) - {}'.format(table)
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
			if temp_group.find('моп')>=0:
				continue

			if temp_group.find('апартаменты')>=0 or temp_group.find('квартира')>=0 or temp_group.find('гостиничный номер')>=0 or temp_group.find('пентхаус')>=0:
				
				flat = rooms[section][group]
				
				for room in flat:
					for sec_room in flat:
						if room.type != sec_room.type:
							room.ex +=1
							
				if len(flat)>0 and flat[0].ex>0:
					flat.sort(key=lambda k: k.ex)
					check = False
					for idx,room in enumerate(flat):
						if check:
									#print 'Ну это вообще: '+room.stage+'_'+room.level+'_'+room.id
							room.append_exception('Несоответствие параметров "КГ_Имя подгруппы помещений" и "КГ_Тип помещения"')
							if room not in errors:
								errors.append(room)
						else:
							try:
								if flat[idx+1].ex > room.ex:
									check = True
							except:
								pass
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
		s = self.__obj.LookupParameter('Стадия')
		if s:
			return s.AsValueString()
		else:
			return "Нет"
	
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
			
			
			TZ_short = self.get_parameter('КГ_Площадь кв. по ТЗ')
			if TZ_short:
				self.set_parameter('Speech_Площадь кв. по ТЗ', TZ_short.AsString())

			try:
				#КГ_Площадь кв. жилая по ТЗ мин.
				TZ_min = self.get_parameter('КГ_Площадь кв. жилая по ТЗ мин.').AsString()
				self.set_parameter('Speech_Площадь кв. жилая по ТЗ мин.', TZ_min)
			except Exception:
				pass


def GetSpacesSquare():
	areas = [CastRoom(x) for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Areas).ToElements()]
	areas = list(filter(lambda x: x.phase == 'Межквартирные перегородки',areas))
	areas = GroupByParameter(areas, func = lambda x: x.level)
	for level in areas:
		areas[level] = GroupByParameter(areas[level], func = lambda x: x.section)
		for section in areas[level]:
			areas[level][section] = GroupByParameter(areas[level][section], func = lambda x: x.group)

			# for group in areas[level][section]:
			# 	flat = areas[level][section][group]
			# 	square = 0.0

			# 	for room in flat:
			# 		square += (round(room.area*0.3048*0.3048,EPS))/(0.3048*0.3048)
				
			# 	areas[level][section][group] = square
	
	return areas




##########################################################################
#---------------------------------MAIN-----------------------------------#
##########################################################################
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument

LEVEL = []
SPACE = False #площадь по пятну
EPS = 0 #число знаков после запятой
errors = [] #Список ошибок
##########################################################################
#-------------------------Проверка спецификаций--------------------------#
##########################################################################
tables_err = any([errCollector.tables[x] for x in errCollector.tables])
if tables_err:
	error_table_print(errCollector.tables)
	
fields_err = sum([len(errCollector.fields[x]) for x in errCollector.fields])
if fields_err:
	error_field_print(errCollector.fields)
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
	SPACE = res['space']
	EPS = res['eps']
	SELECTION = res['selection']
else:
	raise SystemExit(1)
if SELECTION:
	rooms = [ CastRoom(doc.GetElement(elId)) for elId in __revit__.ActiveUIDocument.Selection.GetElementIds() if isinstance(doc.GetElement( elId ), Room) ]
else:
	rooms = [CastRoom(x) for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).ToElements()]
spaces = GetSpacesSquare()

##########################################################################
#-------------------Подбор нужных дверей---------------------------------#
##########################################################################
phase = GetPhaseId('Проект', doc)
ops = [x.name for x in ops if x.elevation*0.3048*0.3048>=2]

doors = FilteredElementCollector(doc).OfClass(FamilyInstance).OfCategory(BuiltInCategory.OST_Doors).ToElements()

if SELECTION:
	roomIds = [room.id for room in rooms]
	temp = []
	for door in doors:
		try: 
			troomId = door.ToRoom[phase].Id.ToString()
			froomId = door.FromRoom[phase].Id.ToString()
			if (troomId in roomIds) or (froomId in roomIds):
				temp.append(door)
		except Exception:
			pass
	doors = temp
else:
	doors = [door for door in doors]

doors = GroupByParameter(doors, func = lambda x: x.LookupParameter('Уровень').AsValueString())
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
if SELECTION:
	LEVEL = [x for x in rooms]

for level in LEVEL:
	if level not in rooms:
		rooms[level] = []

	rooms[level] = GroupByParameter(rooms[level], func = lambda x: x.section)
	for section in rooms[level]:
		rooms[level][section] = GroupByParameter(rooms[level][section], func = lambda x: x.group)
		if SELECTION:
			for group in rooms[level][section]:
				if level in spaces:
					if section in spaces[level]:
						if group in spaces[level][section]: 
							rooms[level][section][group] = rooms[level][section][group] + spaces[level][section][group]
##########################################################################
#-------------------Проверка избыточных и неокруженных-------------------#
##########################################################################
opt = SpatialElementBoundaryOptions()

for level in LEVEL:
	for section in rooms[level]:
		for group in rooms[level][section]:
			for room in rooms[level][section][group]:
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
	error_print(errors, True)
##########################################################################
#----------------------Проверка Параметров-------------------------------#
##########################################################################
for level in LEVEL:
	for section in rooms[level]:
		for group in rooms[level][section]:
			for room in rooms[level][section][group]:
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
	error_print(errors, True)

##########################################################################
#-------------------Оставляем две последние стадии-----------------------#
##########################################################################
del_num = {} #Список неразмещенных помещений
ost_rooms ={}
for level in LEVEL:
	del_num[level] = []
	ost_rooms[level] = []
	for section in rooms[level]:
		for group in rooms[level][section]:
			tempGroup = []
			for room in rooms[level][section][group]:
				temp = [room.phase == 'Проект', room.phase == 'Межквартирные перегородки']
				if not any(temp):
					ost_rooms[level].append(room)
				else:
					tempGroup.append(room)
			rooms[level][section][group] = tempGroup

for level in LEVEL:
	for id in del_num[level]:
		del rooms[level][id]
##########################################################################
#-------------------Проверка Корпус.Секция-------------------------------#
##########################################################################
'''
ДОБАВИТЬ ПРОВЕРКУ ЧЕРЕЗ ОКНА
'''

for level in LEVEL:
	if level in ops:
		if level in doors:
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
	error_print(errors, stopWork = False)
	errors = []
##########################################################################
#-------------------Группировка по квартирам и секциям-------------------#
##########################################################################
# for level in LEVEL:
# 	rooms[level] = GroupByParameter(rooms[level], func = lambda x: x.section)
# 	for section in rooms[level]:
# 		rooms[level][section] = GroupByParameter(rooms[level][section], func = lambda x: x.group)
##########################################################################
#-------------------Проверка на имя подгруппы и тип помещения------------#
##########################################################################
for level in LEVEL:
	# for section in rooms[level]:
	# 	for group in rooms[level][section]:
	# 	print rooms[level][section][group]
		errors += error_finder_ver_2(rooms[level])#[section][group])
if errors:
	error_print(errors, True)
##########################################################################
#-------------------Установка строковых параметров Speech----------------#
##########################################################################
tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Calculating")
t.Start()

for level in LEVEL:
	for section in rooms[level]:
		for group in rooms[level][section]:
			flat = rooms[level][section][group]
			for room in flat:
				if room.phase == 'Проект':
					room.set_parameters()

t.Commit()
tg.Assimilate()
##########################################################################
#-------------------------Расчет площадей--------------------------------#
##########################################################################
tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Calculating")
t.Start()
#По пятну
if SPACE:
	for level in LEVEL:
		for section in rooms[level]:
			for group in rooms[level][section]:
				flat = rooms[level][section][group]
				area = 0
				for room in flat:
					if room.phase == 'Межквартирные перегородки':
						area += (round(room.area*0.3048*0.3048,EPS))/(0.3048*0.3048)

				for room in flat:
					if room.phase == 'Проект':
						room.set_parameter('Speech_Площадь квартиры по пятну', area)
#С коэффициентом
areas = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Areas).ToElements()
areas = GroupByParameter(areas, func = lambda x: x.LookupParameter('Уровень').AsValueString())
for level in LEVEL:
	for room in ost_rooms[level]:
		sq = round((room.get_parameter("Площадь").AsDouble()*0.3048*0.3048),EPS)/(0.3048*0.3048)
		k = room.get_parameter('Speech_Площадь с коэффициентом')
		if k:
			k.Set(sq)
	for level in areas:
		for area in areas[level]:
			sq = round((area.LookupParameter("Площадь").AsDouble()*0.3048*0.3048),EPS)/(0.3048*0.3048)
			k = area.LookupParameter('Speech_Площадь с коэффициентом')
			if k:
				k.Set(sq)
#Квартиры
for level in LEVEL:
	for section in rooms[level]:
		for group in rooms[level][section]:
			flat = rooms[level][section][group]
			area = 0  #прост
			area_kor = 0 #с коэффициентом
			area_living = 0 #жилая
			area_fact = 0 #Фактическая
			for room in flat:
				if room.phase == 'Проект':
					if room.get_parameter("КГ_Открытое_Закрытое").AsString()=="Закрытое":
						area += (round(room.area*0.3048*0.3048,EPS))/(0.3048*0.3048)
						
					area_kor += (round(room.area*room.get_parameter("КГ_Понижающий коэффициент").AsDouble()*0.3048*0.3048,EPS))/(0.3048*0.3048)
					area_fact += (round(room.area*0.3048*0.3048,EPS))/(0.3048*0.3048)
						
					if room.get_parameter("КГ_Жилое_Нежилое").AsString()=="Жилое":
						area_living += (round(room.area*0.3048*0.3048,EPS))/(0.3048*0.3048)
						
			for room in flat:
				if room.phase == 'Проект':
					room.set_parameter('Speech_Площадь квартиры', area)
					room.set_parameter('Speech_Площадь квартиры с коэф.', area_kor)
					room.set_parameter('Speech_Площадь квартиры жилая', area_living)
					room.set_parameter('Speech_Площадь квартиры фактическая', area_fact)
#С коэффициентом и округленная
for level in LEVEL:
	for section in rooms[level]:
		for group in rooms[level][section]:
			flat = rooms[level][section][group]
			for room in flat:
				area_coeff = round((room.get_parameter("КГ_Понижающий коэффициент").AsDouble()*room.area*0.3048*0.3048),EPS)/(0.3048*0.3048)
				room.set_parameter('Speech_Площадь с коэффициентом', area_coeff)
				
				area_rounded = round((room.area*0.3048*0.3048),EPS)/(0.3048*0.3048)
				room.set_parameter('Speech_Площадь округлённая', area_rounded)
t.Commit()
tg.Assimilate()

MessageBox.Show('Готово!')
