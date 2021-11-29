# coding=utf-8
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import math
import os.path as op
import pyevent #pylint: disable=import-error

import System
from System.Diagnostics import Stopwatch
from System.Windows.Input import ICommand
from Autodesk.Revit.DB import *


from pyrevit import forms
from pyrevit import script
from pyrevit.forms import Reactive, reactive
from pyrevit.revit import selection, Transaction

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

log_debug = False
log_point_debug = False
log_elapsed_time_debug = False

text_debug = False
circle_debug = False

eps = 1.0e-9
document = __revit__.ActiveUIDocument.Document


def log_information(message):
    if log_debug:
        print message

def log_point(message):
    if log_point_debug:
        print message

def log_elapsed_time(message):
    if log_elapsed_time_debug:
        print message

def get_next(enumerable, default):
    return next((e for e in enumerable), default)


def is_int(value):
    try:
        int(value)
        return True
    except:
        return False

def create_text(text, location):
    if text_debug:
        options = TextNoteOptions()
        options.Rotation = 0
        #options.TypeId = ElementId(27712)
        options.TypeId = ElementId(366012)
        options.VerticalAlignment = VerticalTextAlignment.Middle
        options.HorizontalAlignment = HorizontalTextAlignment.Center

        return TextNote.Create(document, document.ActiveView.Id, location, str(text), options)


def create_circle(radius, location):
    if circle_debug:
        plane = Plane.CreateByNormalAndOrigin(XYZ.BasisZ, location)
        arc = Arc.Create(plane, radius, 0, 2 * math.pi)

        return document.Create.NewDetailCurve(document.ActiveView, arc )


def convert_value(value):
    return UnitUtils.ConvertToInternalUnits(value, DisplayUnitType.DUT_MILLIMETERS)


def get_index_point(element, index_points):
    return next((index_point for index_point in index_points if index_point.Filter.PassesFilter(element)), None)


def get_index_points(curve):
    step_size = convert_value(500)
    log_point("step_size: {}".format(step_size))

    create_circle(0.5, curve.GetEndPoint(0))
    log_point("left_point: {}".format(curve.GetEndPoint(0)))

    create_circle(0.5, curve.GetEndPoint(1))
    log_point("right_point: {}".format(curve.GetEndPoint(1)))

    points = curve.Tessellate()
    current_point = curve.GetEndPoint(0)

    index  = 0
    create_text(index, current_point)

    for point in points:
        distance = point.DistanceTo(current_point)
        if distance >= step_size:
            count_points = int(distance / step_size)

            log_point("distance: {}".format(distance))
            log_point("count_points: {}".format(count_points))

            x = current_point.X
            y = current_point.Y
            z = current_point.Z

            x_offset = (point.X - x) / count_points
            y_offset = (point.Y - y) / count_points

            for i in range(count_points):
                x = current_point.X + x_offset
                y = current_point.Y + y_offset

                log_point("point: {}".format(point))
                log_point("current_point: {}".format(current_point))
                log_point("new_point: {}".format(XYZ(x, y, 0)))

                point = XYZ(x, y, z)
                current_point = point
                create_circle(0.5, current_point)

                index += 1
                create_text(index, current_point)

                yield IndexElementPoint(index, current_point)

            continue

    index += 1
    create_text(index, curve.GetEndPoint(1))


def get_index_elements(curve, elements):
    if elements:
        index_points = get_index_points(curve)
        index_points = sorted(index_points, key=lambda x: x.Index)

        for room in elements:
            index_point = get_index_point(room, index_points)
            if index_point:
                yield IndexElement(index_point.Index, room)


class IndexElement:
    def __init__(self, index, element):
        self.Index = index
        self.Element = element


class IndexElementPoint(IndexElement):
    def __init__(self, index, element):
        IndexElement.__init__(self, index, element)
        self.Filter = BoundingBoxContainsPointFilter(element)


class MainWindow(forms.WPFWindow):
    def __init__(self,):
        self._context = None
        self.xaml_source = op.join(op.dirname(__file__), 'MainWindow.xaml')
        super(MainWindow, self).__init__(self.xaml_source)

    def ButtonOK_Click(self, sender, e):
        self.Close()

    def ButtonCancel_Click(self, sender, e):
        self.Close()


class RevitRepository:
    def __init__(self, document, ui_application):
        self.__document = document
        self.__application = ui_application

        self.__room_elements = self.get_elements(self.get_category_name(BuiltInCategory.OST_Rooms))
        self.__parking_elements = self.get_elements(self.get_category_name(BuiltInCategory.OST_Parking))

    def get_category(self, category):
        return self.__document.Settings.Categories.Item[category]

    def get_categories(self):
        if self.__room_elements:
            yield self.get_category_name(BuiltInCategory.OST_Rooms)

        if self.__parking_elements:
            yield self.get_category_name(BuiltInCategory.OST_Parking)

    def get_phases(self, category):
        elements = self.get_elements(category)
        return set(sorted((self.get_phase(element) for element in elements)))

    def get_params(self, category):
        element = get_next(self.get_elements(category), None)
        if element:
            return set(sorted((param.Definition.Name for param in element.Parameters if param.StorageType == StorageType.String)))

        return set()

    def get_families(self, category):
        elements = self.get_elements(category)
        return set(sorted([self.get_family(element) for element in elements]))

    def get_elements(self, category):
        if category and isinstance(category, str):
            category = self.get_category(category)
            level_id = self.__document.ActiveView.GenLevel.Id
            elements = FilteredElementCollector(self.__document)\
                .WhereElementIsNotElementType()\
                .OfCategoryId(category.Id)\
                .ToElements()

            return [element for element in elements if element.LevelId == level_id]

        if category == BuiltInCategory.OST_Rooms:
            return self.__room_elements

        if category == BuiltInCategory.OST_Parking:
            return self.__parking_elements

        return set()

    def get_default_param(self, category):
        if category:
            category = self.get_category(category)
            if category.Id == ElementId(BuiltInCategory.OST_Rooms):
                return LabelUtils.GetLabelFor(BuiltInParameter.ROOM_NUMBER)

            if category.Id == ElementId(BuiltInCategory.OST_Parking):
                return LabelUtils.GetLabelFor(BuiltInParameter.DOOR_NUMBER)

    def family_required(self, category):
        if category:
            cat = self.get_category(category)
            if cat.Id == ElementId(BuiltInCategory.OST_Rooms):
                return False

            if cat.Id == ElementId(BuiltInCategory.OST_Parking):
                return True

    @staticmethod
    def get_phase(element):
        if element.Category.Id == ElementId(BuiltInCategory.OST_Rooms):
            return element.GetParam(BuiltInParameter.ROOM_PHASE).AsValueString()

        if element.Category.Id == ElementId(BuiltInCategory.OST_Parking):
            return element.GetParam(BuiltInParameter.PHASE_CREATED).AsValueString()

    @staticmethod
    def get_family(element):
        if element.Category.Id == ElementId(BuiltInCategory.OST_Parking):
            return element.GetParam(BuiltInParameter.ELEM_FAMILY_PARAM).AsValueString()

    @staticmethod
    def get_category_name(category):
        return LabelUtils.GetLabelFor(category)

    @staticmethod
    def pick_element(title):
        with forms.WarningBar(title=title):
            return selection.pick_element(title)


class MainWindowViewModel(Reactive) :
    def __init__(self, view, *args):
        Reactive.__init__(self, *args)

        self.__curve = None
        self.__element_name = None
        self.__revit_repository = RevitRepository(document, __revit__)

        self.start_number = "1"

        self.__prefix = ""
        self.__suffix = ""

        self.__error_text = ""
        self.__family_required = None
        self.__numerate_command = NumerateRoomsCommand(self, self.__revit_repository)
        self.__select_line_command = SelectLineCommand(view, self, self.__revit_repository)

        self.__phase_names = []
        self.__phase_name = None

        self.__param_names = []
        self.__param_name = None

        self.__family_names = []
        self.__family_name = None

        self.__category_names = set(self.__revit_repository.get_categories())
        self.__category_name = get_next(self.__category_names, None)

        self.OnUpdateCategory(self.__category_name)

    def OnUpdateCategory(self, category):
        self.phase_names = self.__revit_repository.get_phases(self.__category_name)
        self.phase_name = get_next(self.__phase_names, None)

        self.param_name = self.__revit_repository.get_default_param(category)
        self.param_names = self.__revit_repository.get_params(self.__category_name)

        self.family_names = self.__revit_repository.get_families(self.__category_name)
        self.family_name = get_next(self.__family_names, None)

        self.family_required = self.__revit_repository.family_required(category)

    @property
    def element(self):
        return self.__curve

    @element.setter
    def element(self, value):
        self.__curve = value
        self.element_name = "{} ({})".format(str(self.__curve.Id.IntegerValue), self.__curve.Category.Name) if self.__curve else None


    @reactive
    def element_name(self):
        return self.__element_name

    @element_name.setter
    def element_name(self, value):
        self.__element_name = value


    @reactive
    def family_required(self):
        return self.__family_required

    @family_required.setter
    def family_required(self, value):
        self.__family_required = value


    @reactive
    def category_names(self):
        return self.__category_names

    @category_names.setter
    def category_names(self, value):
        self.__category_names = value


    @reactive
    def category_name(self):
        return self.__category_name

    @category_name.setter
    def category_name(self, value):
        self.__category_name = value
        self.OnUpdateCategory(self.__category_name)


    @reactive
    def phase_names(self):
        return self.__phase_names

    @phase_names.setter
    def phase_names(self, value):
        self.__phase_names = value


    @reactive
    def phase_name(self):
        return self.__phase_name

    @phase_name.setter
    def phase_name(self, value):
        self.__phase_name = value


    @reactive
    def start_number(self):
        return self.__start_number

    @start_number.setter
    def start_number(self, value):
        self.__start_number = value


    @reactive
    def prefix(self):
        return self.__prefix

    @prefix.setter
    def prefix(self, value):
        self.__prefix = value


    @reactive
    def suffix(self):
        return self.__suffix

    @suffix.setter
    def suffix(self, value):
        self.__suffix = value


    @reactive
    def param_names(self):
        return self.__param_names

    @param_names.setter
    def param_names(self, value):
        self.__param_names = value


    @reactive
    def param_name(self):
        return self.__param_name

    @param_name.setter
    def param_name(self, value):
        self.__param_name = value


    @reactive
    def family_names(self):
        return self.__family_names

    @family_names.setter
    def family_names(self, value):
        self.__family_names = value


    @reactive
    def family_name(self):
        return self.__family_name

    @family_name.setter
    def family_name(self, value):
        self.__family_name = value


    @reactive
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value


    @property
    def numerate_command(self):
        return self.__numerate_command

    @property
    def select_line_command(self):
        return self.__select_line_command


class NumerateRoomsCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, revit_repository, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model
        self.__revit_repository = revit_repository
        self.__view_model.PropertyChanged += self.ViewModel_PropertyChanged

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def ViewModel_PropertyChanged(self, sender, e):
        self.OnCanExecuteChanged()

    def CanExecute(self, parameter):
        if not self.__view_model.element:
            self.__view_model.error_text = "Выберите линию."
            return False

        if not isinstance(self.__view_model.element, CurveElement):
            self.__view_model.error_text = "Выбранный элемент должен быть линией."
            return False

        if not self.__view_model.category_name:
            self.__view_model.error_text = "Категория должна быть заполнена."
            return False

        if not self.__view_model.phase_name:
            self.__view_model.error_text = "Стадия должна быть заполнена."
            return False

        if not is_int(self.__view_model.start_number):
            self.__view_model.error_text = "Начальный номер должен быть числом."
            return False

        if not self.__view_model.param_name:
            self.__view_model.error_text = "Параметр должен быть заполнен."
            return False

        if not self.__view_model.family_name and self.__is_required_family():
            self.__view_model.error_text = "Семейство должно быть заполнено."
            return False

        if int(self.__view_model.start_number) <= 0:
            self.__view_model.error_text = "Начальный номер должен быть положительным числом."
            return False

        self.__view_model.error_text = None
        return True

    def Execute(self, parameter):
        output = script.get_output()
        stopwatch = Stopwatch.StartNew()

        view_model = self.__view_model
        elements = self.__revit_repository.get_elements(view_model.category_name)
        elements = [element for element in elements if self.__get_phase_name(element) == view_model.phase_name ]

        if self.__family_required(view_model.category_name):
            elements = [element for element in elements if self.__get_family(element) == view_model.family_name]

        try:
            curve = view_model.element.Location.Curve
            with Transaction("BIM: Нумерация по линии"):
                index_rooms = get_index_elements(curve, elements)
                index_rooms = sorted(index_rooms, key=lambda x: x.Index)

                index = int(view_model.start_number)
                for room in index_rooms:
                    room.Element.SetParamValue(view_model.param_name,
                                               view_model.prefix + str(index) + view_model.suffix)
                    log_information(
                        "Id: {} ComputedIndex: {} Index: {}".format(output.linkify(room.Element.Id), room.Index, index))

                    index += 1
        finally:
            stopwatch.Stop()
            log_elapsed_time("Operations Elapsed: {}".format(stopwatch.Elapsed))


    def __is_required_family(self):
        return self.__revit_repository.family_required(self.__view_model.category_name)

    def __get_phase_name(self, element):
        return self.__revit_repository.get_phase(element)

    def __get_family(self, element):
        return self.__revit_repository.get_family(element)

    def __family_required(self, category):
        return self.__revit_repository.family_required(category)


class SelectLineCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view, view_model, revit_repository, *args):
        ICommand.__init__(self, *args)
        self.__view = view
        self.__view_model = view_model
        self.__revit_repository = revit_repository

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):
        self.__view.Hide()
        try:
            self.__view_model.element = self.__revit_repository.pick_element("Выберите линию.")
        finally:
            self.__view.show_dialog()

def execute():
    main_window = MainWindow()
    main_window.DataContext = MainWindowViewModel(main_window)
    main_window.show_dialog()


execute()