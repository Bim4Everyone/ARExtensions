# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

clr.AddReference("FormsCollector")
from FormsCollector import RenumerateVectorForm

clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox

from pyrevit import EXEC_PARAMS

from Autodesk.Revit.DB.Architecture import Room
from Autodesk.Revit.DB import *

from pyrevit.revit import Transaction

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *

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
        self.obj.Parameter[BuiltInParameter.ROOM_NUMBER].Set(num)


def renumber_rooms(rooms_revit, start, suffix, prefix, direction):
    fix_param = "Speech_Фиксация номера пом."

    placed_number = []
    rooms_to_num = []
    rooms = [GeometryRoom(x, direction) for x in rooms_revit]

    if rooms[0].obj.LookupParameter(fix_param):
        for room in rooms:
            if room.obj.LookupParameter(fix_param).AsInteger() == 0:
                rooms_to_num.append(room)
            else:
                placed_number.append(room.obj.Parameter[BuiltInParameter.ROOM_NUMBER].AsString())

    rooms_to_num.sort(key=lambda k: k.range)

    with Transaction("BIM: Нумерация по диагонали"):
        for i in range(len(rooms_to_num)):
            number = start + i
            while str(number) in placed_number:
                number += 1
            number = str(number)
            placed_number.append(number)
            name = "{}{}{}".format(prefix, number, suffix)
            rooms_to_num[i].set_num(name)


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    selection_ids = uidoc.Selection.GetElementIds()
    selection = [doc.GetElement(i) for i in selection_ids]
    rooms = [x for x in selection if isinstance(x, Room)]
    if not rooms:
        MessageBox.Show("Необходимо выбрать помещения!")
        raise SystemExit(1)

    form = RenumerateVectorForm()
    result = form.ShowDialog()
    if not result:
        raise SystemExit(1)

    start = form.Result.Start
    suffix = form.Result.Suffix
    prefix = form.Result.Prefix
    direction = form.Result.Direction

    renumber_rooms(rooms, start, suffix, prefix, direction)


script_execute()
