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
        self.selected_groups = [x.Name for x in self.RoomGroups.Items if x.IsChecked]
        self.Close()

    def select_all(self, sender, args):
        new_items = []
        for group in self.RoomGroups.ItemsSource:
            group.IsChecked = True
            new_items.append(group)
        self.RoomGroups.ItemsSource = new_items

    def deselect_all(self, sender, args):
        new_items = []
        for group in self.RoomGroups.ItemsSource:
            group.IsChecked = False
            new_items.append(group)
        self.RoomGroups.ItemsSource = new_items

    def invert(self, sender, args):
        new_items = []
        for group in self.RoomGroups.ItemsSource:
            group.IsChecked = not(group.IsChecked)
            new_items.append(group)
        self.RoomGroups.ItemsSource = new_items


class RoomGroup:
    def __init__(self, group):
        self.Name = group
        self.IsChecked = True


class GeometryRoom:
    def __init__(self, obj, direction):
        self.x = obj.Location.Point.X
        self.y = obj.Location.Point.Y
        self.obj = obj
        self.direction = direction

        self.range = self.x * self.direction.X - self.y * self.direction.Y

    def set_num(self, num):
        self.obj.Number = num

    def get_num(self):
        return self.obj.Number


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
        rooms = [GeometryRoom(x, self.direction) for x in self.rooms_revit]

        for room in rooms:
            if room.obj.GetParamValueOrDefault(ProjectParamsConfig.Instance.IsRoomNumberFix):
                self.placed_number.append(room.get_num())
            else:
                self.rooms_to_num.append(room)

        self.rooms_to_num.sort(key=lambda k: k.range)

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
    rooms = [x for x in selection if isinstance(x, Room)]
    if not rooms:
        alert("Необходимо выбрать помещения!", exitscript=True)

    group_param = ProjectParamsConfig.Instance.RoomGroupName
    groups = {doc.GetElement(r.GetParamValueOrDefault(group_param)).Name for r in rooms}
    groups = sorted(groups)
    groups = {RoomGroup(x) for x in groups}

    main_window = MainWindow(groups)
    main_window.show_dialog()
    filtered_groups = main_window.selected_groups

    if filtered_groups:
        filtered_rooms = []
        for room in rooms:
            if doc.GetElement(room.GetParamValueOrDefault(group_param)).Name in filtered_groups:
                filtered_rooms.append(room)

        if filtered_rooms:
            form = RenumerateVectorForm()
            result = form.ShowDialog()
            if not result:
                raise SystemExit(1)

            numerate_info = NumerateInfo(form)

            rooms_numerator = RoomsNumerator(numerate_info, filtered_rooms)
            rooms_numerator.renumber_rooms()


script_execute()
