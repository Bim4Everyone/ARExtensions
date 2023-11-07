# coding=utf-8

import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import dosymep

clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from Autodesk.Revit.DB import *

from pyrevit import forms
from pyrevit import revit
from pyrevit import script
from pyrevit import EXEC_PARAMS

from dosymep_libs.bim4everyone import *

doc = __revit__.ActiveUIDocument.Document


def collect_rooms():
    '''
    Функция возвращает размещенные помещения, у которых значение параметра "Площадь" не равно 0
    '''
    all_rooms = FilteredElementCollector(doc).WhereElementIsNotElementType().OfCategory(
        BuiltInCategory.OST_Rooms).ToElements()
    correct_rooms = [room for room in all_rooms if
                     room.Location is not None and room.get_Parameter(BuiltInParameter.ROOM_AREA).AsDouble != 0]
    return correct_rooms


# def check_no_rooms_alert():
#     all_rooms = FilteredElementCollector(doc).WhereElementIsNotElementType().OfCategory(
#         BuiltInCategory.OST_Rooms).ToElements()
#     no_rooms_ckeck = all([True if room is None or room.Location is None else False for room in all_rooms])
#     return no_rooms_ckeck


def check_active_view_not_plan():
    active_view_type = doc.ActiveView.ViewType
    return active_view_type != ViewType.FloorPlan


def check_rooms():
    all_rooms = FilteredElementCollector(doc).WhereElementIsNotElementType().OfCategory(
        BuiltInCategory.OST_Rooms).ToElements()
    count_of_correct = 0
    count_of_incorrect = 0
    for room in all_rooms:
        area = room.get_Parameter(BuiltInParameter.ROOM_AREA).AsDouble()
        print(area)
        if area == 0:
            count_of_incorrect += 1
        else:
            count_of_correct += 1


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    all_rooms = collect_rooms()

    # Первоначальные проверки на размещенные помещения с площадью != и активный вид
    if len(all_rooms) == 0:
        forms.alert("В проекте отсутствуют размещенные помещения")
        return

    if check_active_view_not_plan():
        forms.alert("Для запуска плагина перейдите на план этажа!")
        return


script_execute()
