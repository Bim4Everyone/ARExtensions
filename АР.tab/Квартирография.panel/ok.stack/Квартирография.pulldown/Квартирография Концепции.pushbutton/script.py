# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
import clr
from pyrevit import revit
clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox
clr.AddReference('System')
from System.Collections.Generic import List 

__doc__ = '''Считает площадь квартир. Упрощенная версия квартирографии. 

Заполняет следующие параметры площадей помещений:
Speech_Площадь квартиры с коэф.

Speech_Площадь с коэффициентом
Speech_Площадь округлённая
'''

from Autodesk.Revit.DB import Wall, GroupType, FilteredElementCollector, Location, Transaction, TransactionGroup, LocationCurve, ViewSchedule, StorageType, Phase,Reference, Options, XYZ, FamilyInstance , Level, BuiltInCategory, ElementTransformUtils, CopyPasteOptions, ElementId, ScheduleFieldType
from Autodesk.Revit.UI.Selection import ObjectType, ObjectSnapTypes

from pyrevit import forms
from pyrevit.framework import Controls
from pySpeech.configkeeper import ConfigKeeper

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
		self.Title = "Квартирография Концепции"
		self._verify_context()
		self._list_options()		
		self._load_config()
	
	def _load_config(self):
		configKeeper = ConfigKeeper()

		if "purpose_стадияК" in configKeeper:
			self.purpose.SelectedIndex  = configKeeper["purpose_стадияК"]

	def _update_config(self):
		configKeeper = ConfigKeeper()
		configKeeper["purpose_стадияК"] = int(self.purpose.SelectedIndex)
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
						'eps':int(self.purpose.Text)}
		self._update_config()
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


	
def getProjectParameters():
	fileName = 'W:\\BIM-Ресурсы\\Revit - 2 Стандарты\\!ФОП\\Параметры проекта '+app.VersionNumber+'.rvt'
	docFamily = app.OpenDocumentFile(fileName)
	
	schedules  = [x for x in FilteredElementCollector(docFamily).OfClass(ViewSchedule).ToElements() if x.Name == '111 - Квартирография Концепция']

	ids = List[ElementId]([x.Id for x in schedules])
	tg = TransactionGroup(doc, "Update")
	tg.Start()
	t = Transaction(doc, "Update Sheet Parmeters")
	t.Start()

	option = CopyPasteOptions()


	ElementTransformUtils.CopyElements(docFamily, ids, doc, None, option)

	schedules  = [x for x in FilteredElementCollector(doc).OfClass(ViewSchedule).ToElements() if x.Name == '111 - Квартирография Концепция']
	ids = List[ElementId]([x.Id for x in schedules])
	doc.Delete(ids)

	t.Commit()
	tg.Assimilate()

	docFamily.Close(saveModified = False)
	
	schedules  = [x for x in FilteredElementCollector(doc).OfClass(ViewSchedule).ToElements() if x.Name.find('КГ (Ключ.) - Тип помещения')>=0]
	el = schedules[0]

	newField = None


	for field in el.Definition.GetSchedulableFields():
		if field.FieldType == ScheduleFieldType.Instance:
			parameterId = field.ParameterId
			fieldName = field.GetName(doc)
			if fieldName == 'КГ_Площадь кв. по ТЗ':
				newField = field
				break
	tg = TransactionGroup(doc, "Update")
	tg.Start()
	t = Transaction(doc, "Update Sheet Parmeters")
	t.Start()

	try:
		el.Definition.AddField(newField)
	except:
		pass

	t.Commit()
	tg.Assimilate()	
	
class CastRoom(object):
	ex = 0
	
	def __init__(self, obj):
		self.__obj = obj
		self.__exceptions = []
		
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
			TZ_short = self.get_parameter('КГ_Площадь кв. по ТЗ').AsString()
			self.set_parameter('Speech_Площадь кв. по ТЗ', TZ_short)
		except Exception:
			file = app.OpenSharedParameterFile()
			group = file.Groups.get_Item("Квартирография")
			definition = group.Definitions.get_Item( "Speeech_Площадь кв. по ТЗ" )
			cats = app.Create.NewCategorySet()
			cats.Insert(doc.Settings.Categories.get_Item(BuiltInCategory.OST_Rooms))
			
			bind = app.Create.NewInstanceBinding(cats)

			tg = TransactionGroup(doc, "Update")
			tg.Start()
			t = Transaction(doc, "Update Sheet Parmeters")
			t.Start()

			doc.ParameterBindings.Insert(definition, bind, BuiltInParameterGroup.INVALID)

			t.Commit()
			tg.Assimilate()
			
			self.set_parameter('Speech_Площадь кв. по ТЗ', TZ_short)
			
			
			
			
def GroupByParameter(lst, func):
	res = {}
	for el in lst:
		key = func(el)
		if key in res:
			res[key].append(el)
		else:
			res[key] = [el]
	return res

##########################################################################
#---------------------------------MAIN-----------------------------------#
##########################################################################
doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = doc.Application

LEVEL = []
EPS = 0 #число знаков после запятой
errors = [] #Список ошибок
contin = False
##########################################################################
#---------------------Проверка наличия параметров------------------------#
##########################################################################
rooms = [CastRoom(x) for x in FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).ToElements()]
for room in rooms:
	try:
		room.get_parameter('КГ_Площадь кв. по ТЗ').AsString()
		contin = True
		break
	except Exception:
		getProjectParameters()
		print '|{:-^40}|'.format('')
		print '|{:-^40}|'.format('ВНИМАНИЕ')
		print '|{:-^40}|'.format('ЗАПОЛНИТЕ: КГ_Площадь кв. по ТЗ')
		print '|{:-^40}|'.format('В ТАБЛИЦЕ: *_КГ (Ключ.) - Тип помещения')
		print '|{:-^40}|'.format('')
		break
		

##########################################################################
#-------------------------Ввод параметров--------------------------------#
##########################################################################
lvls = FilteredElementCollector(doc).OfClass(Level)
#LEVEL = lvls
ops = [Option(x) for x in lvls] 
ops.sort(key=lambda x: x.elevation)
if contin:
	res = SelectLevelFrom.show(ops,
					button_name='Рассчитать')
else:
	res = False

if res:
	LEVEL = [x.name for x in res['level']]
	EPS = res['eps']

##########################################################################
#-------------------Группировка по уровню--------------------------------#
##########################################################################

# for level in LEVEL:
	# print(level)
rooms = GroupByParameter(rooms, func = lambda x: x.level)
for level in LEVEL:
	if level not in rooms:
		rooms[level] = []
##########################################################################
#----------------------Проверка Параметров-------------------------------#
##########################################################################
for level in LEVEL:
	for room in rooms[level]:

		if room.name == '(нет)' or not room.name:
			room.append_exception('КГ_Наименование *не заполнено*')
			if room not in errors:
				errors.append(room)

		if room.section == '(нет)' or not room.section:
			room.append_exception('КГ_Корпус.Секция *не заполнено*')
			if room not in errors:
				errors.append(room)

		if room.phase == 'Шахты' or room.phase == 'Контур здания':
			continue

		if room.type == '(нет)' or not room.type:
			room.append_exception('КГ_Тип помещения *не заполнено*')
			if room not in errors:
				errors.append(room)
		if room.group == '(нет)' or not room.group:
			room.append_exception('КГ_Имя подгруппы помещений *не заполнено*')
			if room not in errors:
				errors.append(room)
if errors:
	error_print(errors)
	
# ##########################################################################
# #-------------------Установка строковых параметров Speech----------------#
# ##########################################################################
tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Calculating")
t.Start()

for level in LEVEL:
	for room in rooms[level]:
		room.set_parameters()

t.Commit()
tg.Assimilate()
##########################################################################
#-------------------------По стадиям-------------------------------------#
##########################################################################
for level in LEVEL:
	rooms[level] = GroupByParameter(rooms[level], func = lambda x: x.phase)
	for phase in rooms[level]:
		rooms[level][phase] = GroupByParameter(rooms[level][phase], func = lambda x: x.section)
		for section in rooms[level][phase]:
			rooms[level][phase][section] = GroupByParameter(rooms[level][phase][section], func = lambda x: x.group)
##########################################################################
#-------------------------Расчет площадей--------------------------------#
##########################################################################
'''
tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Calculating")
t.Start()

for level in LEVEL:
	for room in rooms[level]:
		area = round(room.area*0.3048*0.3048,EPS)/(0.3048*0.3048)
		room.set_parameter('Speech_Площадь с коэффициентом', area)
t.Commit()
tg.Assimilate()
if LEVEL:
	MessageBox.Show('Готово!')
'''

tg = TransactionGroup(doc, "Update")
tg.Start()
t = Transaction(doc, "Calculating")
t.Start()

for level in LEVEL:
	for phase in rooms[level]:
		for section in rooms[level][phase]:
			for group in rooms[level][phase][section]:
				
				area = 0
				for room in rooms[level][phase][section][group]:
					room_area = room.area*room.get_parameter('КГ_Понижающий коэффициент').AsDouble()
					room_area = round(room_area*0.3048*0.3048,EPS)/(0.3048*0.3048)
					area += room_area
					room.set_parameter('Speech_Площадь с коэффициентом', room_area)
					
					area_rounded = round((room.area*0.3048*0.3048),EPS)/(0.3048*0.3048)
					room.set_parameter('Speech_Площадь округлённая', area_rounded)
					
				for room in rooms[level][phase][section][group]:
					room.set_parameter('Speech_Площадь квартиры с коэф.', area)
				
t.Commit()
tg.Assimilate()
if LEVEL:
	MessageBox.Show('Готово!')



				

				
