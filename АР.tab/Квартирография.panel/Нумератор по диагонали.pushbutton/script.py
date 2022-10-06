# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

clr.AddReference("FormsCollector")
from FormsCollector import RenumerateVectorForm

clr.AddReference("System.Windows.Forms")

from pyrevit import forms
from pyrevit import EXEC_PARAMS

from Autodesk.Revit.DB.Architecture import Room
from Autodesk.Revit.DB import *

from pyrevit.revit import Transaction

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.ProjectParams import *

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


class GeometryRoom:
    def __init__(self, obj, direction):
        self.x = obj.Location.Point.X
        self.y = obj.Location.Point.Y
        self.obj = obj
        self.direction = direction

        self.range = self.x * self.direction.X - self.y * self.direction.Y

    def set_num(self, num):
        self.obj.SetParamValue("Номер", num)


class NumerateInfo:
    def __init__(self, form):
        self.start = form.Result.Start
        self.suffix = form.Result.Suffix
        self.prefix = form.Result.Prefix
        self.direction = form.Result.Direction


class RoomsNumerator:
    def __init__(self, renumerate_info, rooms):
        self.start = renumerate_info.start
        self.suffix = renumerate_info.suffix
        self.prefix = renumerate_info.prefix
        self.direction = renumerate_info.direction
        self.rooms_revit = rooms

        self.placed_number = []
        self.rooms_to_num = []

        self.__sort_rooms()
        self.__renumber_rooms()

    def __sort_rooms(self):
        rooms = [GeometryRoom(x, self.direction) for x in self.rooms_revit]

        if doc.IsExistsParam(ProjectParamsConfig.Instance.IsRoomNumberFix):
            for room in rooms:
                if not room.obj.GetParamValue(ProjectParamsConfig.Instance.IsRoomNumberFix):
                    self.rooms_to_num.append(room)
                else:
                    self.placed_number.append(room.obj.GetParamValue("Номер"))
        else:
            self.rooms_to_num = rooms

        self.rooms_to_num.sort(key=lambda k: k.range)

    def __renumber_rooms(self):
        with Transaction("BIM: Нумерация по диагонали"):
            for i, room in enumerate(self.rooms_to_num):
                number = self.start + i
                while str(number) in self.placed_number:
                    number += 1
                number = str(number)
                self.placed_number.append(number)
                name = "{}{}{}".format(self.prefix, number, self.suffix)
                room.set_num(name)


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    selection_ids = uidoc.Selection.GetElementIds()
    selection = [doc.GetElement(i) for i in selection_ids]
    rooms = [x for x in selection if isinstance(x, Room)]
    if not rooms:
        forms.alert("Необходимо выбрать помещения!")
        raise SystemExit(1)

    form = RenumerateVectorForm()
    result = form.ShowDialog()
    if not result:
        raise SystemExit(1)

    numerate_info = NumerateInfo(form)

    RoomsNumerator(numerate_info, rooms)


script_execute()
