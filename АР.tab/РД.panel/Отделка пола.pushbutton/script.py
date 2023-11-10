# coding=utf-8

import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import dosymep.Revit

clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from Autodesk.Revit.DB import *
from Autodesk.Revit.DB.Architecture import RoomFilter
from pyrevit import forms
from pyrevit import revit
from pyrevit import script
from pyrevit import EXEC_PARAMS
from pyrevit.revit import HOST_APP

from dosymep_libs.bim4everyone import *

doc = __revit__.ActiveUIDocument.Document


def elements_to_list(elements):
    res_list = []
    for curve in elements:
        res_list.append(curve)
    return res_list


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


def check_active_view_not_plan():
    active_view_type = doc.ActiveView.ViewType
    return active_view_type != ViewType.FloorPlan


# def floor_create(curve_loop, level_id):
#     floor_type = (FilteredElementCollector(doc)
#                   .WhereElementIsElementType()
#                   .OfCategory(BuiltInCategory.OST_Floors)
#                   .FirstElementId())
#     Floor.Create(doc, curve_loop, floor_type, level_id)

def floor_create(room, floor_type):
    curve_loop = RoomContour(room).get_curves_of_room()
    level_id = room.LevelId
    Floor.Create(doc, curve_loop, floor_type.Id, level_id)


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
    with Transaction(doc, "Скрипт:Тест") as t:
        t.Start()
        for room in all_rooms:
            floor_type = floor_types[0]
            # curve = RoomContour(room).get_curves_of_room()
            # level_id = room.LevelId
            # floor_create(curve, level_id)
            floor_create(room, floor_type)

        t.Commit()


script_execute()
