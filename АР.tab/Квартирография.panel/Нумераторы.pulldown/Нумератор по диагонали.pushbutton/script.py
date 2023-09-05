# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

clr.AddReference("FormsCollector")
from FormsCollector import RenumerateVectorForm

clr.AddReference("System.Windows.Forms")

from pyrevit.forms import *
from pyrevit import EXEC_PARAMS

from Autodesk.Revit.DB import *

from pyrevit import revit

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.ProjectParams import *

from rooms import RevitRepository, RoomGroup, SelectRoomGroupsWindow, GeometryRoom


document = __revit__.ActiveUIDocument.Document


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

    def __sort_rooms(self):
        rooms = [x for x in self.rooms_revit]

        for room in rooms:
            if room.room_obj.GetParamValueOrDefault(ProjectParamsConfig.Instance.IsRoomNumberFix):
                self.placed_number.append(room.get_num())
            else:
                self.rooms_to_num.append(room)

        self.rooms_to_num.sort(key=lambda k: k.get_range(self.direction))

    def renumber_rooms(self):
        self.__sort_rooms()
        with revit.Transaction("BIM: Нумерация по диагонали"):
            for i, room in enumerate(self.rooms_to_num):
                number = self.start + i
                while str(number) in self.placed_number:
                    number += 1
                number = str(number)
                self.placed_number.append(number)
                name = "{}{}{}".format(self.prefix, number, self.suffix)
                room.set_num(name)
            alert("Последний назначенный номер: {}".format(number))


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    revit_repository = RevitRepository(document, __revit__)
    if revit_repository.is_empty:
        alert("Выберите помещения для нумерации", exitscript=True)

    groups = revit_repository.get_rooms_groups()

    select_groups_window = SelectRoomGroupsWindow(groups)
    select_groups_window.show_dialog()
    selected_groups = select_groups_window.selected_groups

    filtered_rooms = revit_repository.get_filtered_room_by_group(selected_groups)

    if filtered_rooms:
        form = RenumerateVectorForm()
        result = form.ShowDialog()
        if not result:
            script.exit()

        numerate_info = NumerateInfo(form)

        rooms_numerator = RoomsNumerator(numerate_info, filtered_rooms)
        rooms_numerator.renumber_rooms()


script_execute()
