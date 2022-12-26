# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

clr.AddReference("FormsCollector")
from FormsCollector import RenumerateVectorForm

clr.AddReference("System.Windows.Forms")

from pyrevit.forms import *
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


class MainWindow(WPFWindow):
    def __init__(self, groups):
        self._context = None
        self.xaml_source = op.join(op.dirname(__file__), 'MainWindow.xaml')
        super(MainWindow, self).__init__(self.xaml_source)

        self.RoomGroups.ItemsSource = groups
        self.selected_groups = None

    def filter_groups(self, sender, args):
        self.selected_groups = [x.name for x in self.RoomGroups.Items if x.is_checked]
        self.Close()

    def update_states(self, value):
        for group in self.RoomGroups.ItemsSource:
            group.is_checked = value

    def select_all(self, sender, args):
        self.update_states(True)

    def deselect_all(self, sender, args):
        self.update_states(False)

    def invert(self, sender, args):
        for group in self.RoomGroups.ItemsSource:
            group.is_checked = not (group.is_checked)


class RoomGroup(Reactive):
    def __init__(self, group):
        self.name = group
        self.__is_checked = True

    @reactive
    def is_checked(self):
        return self.__is_checked

    @is_checked.setter
    def is_checked(self, value):
        self.__is_checked = value


class GeometryRoom:
    def __init__(self, obj):
        self.x = obj.Location.Point.X
        self.y = obj.Location.Point.Y
        self.obj = obj
        self.group_param = ProjectParamsConfig.Instance.RoomGroupName

    def set_num(self, num):
        self.obj.Number = num

    def get_num(self):
        return self.obj.Number

    def get_group(self):
        if self.obj.GetParamValueOrDefault(self.group_param):
            group = doc.GetElement(self.obj.GetParamValueOrDefault(self.group_param))
            if group:
                return group.Name
        return "<Без группы>"

    def get_range(self, direction):
        return self.x * direction.X - self.y * direction.Y


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
            if room.obj.GetParamValueOrDefault(ProjectParamsConfig.Instance.IsRoomNumberFix):
                self.placed_number.append(room.get_num())
            else:
                self.rooms_to_num.append(room)

        self.rooms_to_num.sort(key=lambda k: k.get_range(self.direction))

    def renumber_rooms(self):
        self.__sort_rooms()
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
    rooms = [GeometryRoom(x) for x in selection if isinstance(x, Room)]
    if not rooms:
        alert("Необходимо выбрать помещения!", exitscript=True)

    groups = {r.get_group() for r in rooms}
    groups = sorted(groups)
    groups = {RoomGroup(x) for x in groups}

    main_window = MainWindow(groups)
    main_window.show_dialog()
    filtered_groups = main_window.selected_groups

    filtered_rooms = []
    if filtered_groups:
        for room in rooms:
            if room.get_group() in filtered_groups:
                filtered_rooms.append(room)
    else:
        script.exit()

    if filtered_rooms:
        form = RenumerateVectorForm()
        result = form.ShowDialog()
        if not result:
            script.exit()

        numerate_info = NumerateInfo(form)

        rooms_numerator = RoomsNumerator(numerate_info, filtered_rooms)
        rooms_numerator.renumber_rooms()


script_execute()