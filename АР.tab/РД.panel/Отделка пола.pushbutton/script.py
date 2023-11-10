# coding=utf-8

import clr
import datetime

from System.Collections.Generic import *
from System.Windows.Input import ICommand

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import dosymep.Revit

clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)
from System.Windows.Input import ICommand

import pyevent
from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Architecture import RoomFilter
from pyrevit import forms
from pyrevit.forms import *
from pyrevit import revit
from pyrevit import script
from pyrevit import EXEC_PARAMS, revit
from pyrevit.revit import HOST_APP

from dosymep_libs.bim4everyone import *

doc = __revit__.ActiveUIDocument.Document


def elements_to_list(elements):
    return [el for el in elements]


def convert_value(value):
    if HOST_APP.is_older_than(2022):
        return UnitUtils.ConvertToInternalUnits(value, DisplayUnitType.DUT_MILLIMETERS)
    else:
        return UnitUtils.ConvertToInternalUnits(value, UnitTypeId.Millimeters)


class RoomContour():
    def __init__(self, room):
        self.room = room

    def get_curves_of_room(self):
        spatialElementBoundaryOptions = SpatialElementBoundaryOptions()
        curves = []
        loops = self.room.GetBoundarySegments(spatialElementBoundaryOptions)
        for loop in loops:
            if HOST_APP.is_newer_than(2021):
                curve = CurveLoop()
                for i in range(len(loop)):
                    curve.Append(loop[i].GetCurve())
                curves.append(self.simplify(curve))
            else:
                curve = CurveArray()
                for i in range(len(loop)):
                    curve.Append(loop[i].GetCurve())
                curves.append(curve)
        return curves

    def append_curve(self, curve, next_curve):
        '''
        Создает одну прямую линию из двух, если они являются прямыми и коллинеарными и если конечная точка первой
        совпадает с начальной точкой второй
        curve: текущая кривая
        next_curve: следующая кривая
        return: True, если слияние кривых возможно и прошло успешно, иначе False
        '''
        if curve is not None and next_curve is not None:
            curve_vector = (curve.GetEndPoint(1) - curve.GetEndPoint(0)).Normalize()
            add_curve_vector = (next_curve.GetEndPoint(1) - next_curve.GetEndPoint(0)).Normalize()
            are_collinear = (isinstance(curve, Line) and isinstance(next_curve, Line)) and curve_vector.IsAlmostEqualTo(
                add_curve_vector)
            are_join = curve.GetEndPoint(1).IsAlmostEqualTo(next_curve.GetEndPoint(0))
            if are_collinear and are_join:
                new_curve = Line.CreateBound(curve.GetEndPoint(0), next_curve.GetEndPoint(1))
                return True, new_curve
        return False, curve

    def simplify(self, curve_loop):
        '''
        Соединяет кривые у замкнутой петли (Loop), лежащие на одной прямой и возвращает новую упрощенную
        замкнутую петлю (Loop)
        curve_loop: Замкнутая петля из кривых
        return: Новая петля с оптимизированными кривыми, которые лежали на одной прямой друг за другом
        '''
        simplified_curves = CurveLoop()
        curve_prev = None
        curves_list = elements_to_list(curve_loop)
        for i in range(len(curves_list)):
            curve_current = curves_list[i]
            (curve_added, curve_prev) = self.append_curve(curve_prev, curve_current)
            if curve_prev is None:
                curve_prev = curve_current
                continue
            if i != 0 and i != (len(curves_list) - 1) and (not curve_added):
                simplified_curves.Append(curve_prev)
                curve_prev = curve_current
                continue
            if i == (len(curves_list) - 1):
                if curve_added:
                    curve_prev = curve_added
                    simplified_curves.Append(curve_prev)
                else:
                    simplified_curves.Append(curve_prev)
                    simplified_curves.Append(curve_current)

        return simplified_curves


def collect_rooms():
    '''
    Функция возвращает размещенные помещения, у которых значение параметра "Площадь" не равно 0
    '''
    room_filter = RoomFilter()
    all_rooms = FilteredElementCollector(doc) \
        .WherePasses(room_filter) \
        .ToElements()
    correct_rooms = [room for room in all_rooms if
                     room.Location is not None and room.get_Parameter(BuiltInParameter.ROOM_AREA).AsDouble != 0]
    return correct_rooms


def collect_floor_types():
    all_floor_types = FilteredElementCollector(doc) \
        .WhereElementIsElementType() \
        .OfCategory(BuiltInCategory.OST_Floors)
    return all_floor_types


class CollectRevitInfo:
    def __init__(self):
        self.__floor_types = self.collect_floor_types()

    @reactive
    def floor_types(self):
        return self.__floor_types

    def collect_floor_types(self):
        all_floor_types = FilteredElementCollector(doc) \
            .WhereElementIsElementType() \
            .OfCategory(BuiltInCategory.OST_Floors)
        return all_floor_types


def check_active_view_not_plan():
    active_view_type = doc.ActiveView.ViewType
    return active_view_type != ViewType.FloorPlan


# def floor_create(curve_loop, level_id):
#     floor_type = (FilteredElementCollector(doc)
#                   .WhereElementIsElementType()
#                   .OfCategory(BuiltInCategory.OST_Floors)
#                   .FirstElementId())
#     Floor.Create(doc, curve_loop, floor_type, level_id)

def floor_create(room, floor_type, level_offset=0):
    '''
    Создает перекрытие на основе CurveLoop помещения и его уровня, заданным типоразмером перекрытия со смещением
    от уровня (опционально)
    room: помещение, на основе которого будет создано перекрытие
    floor_type: типоразмер перекрытия, который будет указан для создания
    level_offset: смещение от уровня (по умолчанию 0)
    '''
    curve_loop = RoomContour(room).get_curves_of_room()
    level_id = room.LevelId
    current_floor = Floor.Create(doc, curve_loop, floor_type.Id, level_id)
    level_offset = convert_value(level_offset)
    floor_offset = current_floor.get_Parameter(BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM).Set(level_offset)


class MainWindow(WPFWindow):
    def __init__(self):
        self._context = None
        self.xaml_source = op.join(op.dirname(__file__), "MainWindow.xaml")
        super(MainWindow, self).__init__(self.xaml_source)


class MainWindowViewModel(Reactive):
    def __init__(self, revit_info):
        Reactive.__init__(self)
        self.__revit_info = revit_info
        self.__floor_types = revit_info.floor_types

    @reactive
    def floor_types(self):
        return self.__floor_types


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    all_rooms = collect_rooms()

    # Проверка на неразмещенные помещения с площадью == 0
    if len(all_rooms) == 0:
        forms.alert("В проекте отсутствуют размещенные помещения")
        return

    # Проверка принадлежности активного вида не к Плану этажа
    if check_active_view_not_plan():
        forms.alert("Для запуска плагина перейдите на план этажа!")
        return

    all_floors = collect_floor_types()
    floor_types = elements_to_list(all_floors)
    main_window = MainWindow()
    revit_info = CollectRevitInfo()
    main_window.DataContext = MainWindowViewModel(revit_info)
    main_window.show_dialog()
    with Transaction(doc, "BIM: Отделка пола") as t:
        t.Start()
        for room in all_rooms:
            floor_type = floor_types[0]
            # curve = RoomContour(room).get_curves_of_room()
            # level_id = room.LevelId
            # floor_create(curve, level_id)
            floor_create(room, floor_type)

        t.Commit()


script_execute()
