# coding=utf-8
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

from Autodesk.Revit.DB import *

from pyrevit.forms import *
from pyrevit.forms import Reactive, reactive
from pyrevit.revit import selection, HOST_APP

from dosymep.Bim4Everyone.ProjectParams import *

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

document = __revit__.ActiveUIDocument.Document  # type: Document


class RevitRepository:
    def __init__(self, document, ui_application):
        self.__document = document
        self.__application = ui_application

        self.__elements = [element for element in selection.get_selection().elements
            if element.LevelId == document.ActiveView.GenLevel.Id]

        self.__room_elements = self.get_geometry_elements(BuiltInCategory.OST_Rooms)
        self.__filtered_rooms_by_group = []

        self.room_groups = self.get_rooms_groups()

    @property
    def is_empty(self):
        return not self.__room_elements

    def get_params(self):
        element = get_next(self.__room_elements, None)
        if element:
            return set(sorted((param.Definition.Name for param in element.room_obj.Parameters if param.StorageType == StorageType.String)))
        return set()

    def get_geometry_elements(self, category):
        category = Category.GetCategory(self.__document, category)
        return [GeometryRoom(element) for element in self.__elements if element.Category.Id == category.Id]

    def get_filtered_rooms_by_group(self):
        selected_groups = [x for x in self.room_groups if x.is_checked]
        return [x for x in self.__room_elements if x.get_group() in selected_groups]

    def get_rooms_groups(self):
        groups = set(r.get_group() for r in self.__room_elements)
        return sorted(groups, key=lambda x: x.name)

    def get_default_param(self):
        return LabelUtils.GetLabelFor(BuiltInParameter.ROOM_NUMBER)

    @staticmethod
    def pick_element(title):
        with WarningBar(title=title):
            return selection.pick_element(title)


class GeometryRoom:
    def __init__(self, room_obj):
        self.x = room_obj.Location.Point.X
        self.y = room_obj.Location.Point.Y
        self.room_obj = room_obj

        self.group_param = ProjectParamsConfig.Instance.RoomGroupName

    def set_num(self, num):
        self.room_obj.Number = num

    def get_num(self):
        return self.room_obj.Number

    def get_group(self):
        if self.room_obj.GetParamValueOrDefault(self.group_param):
            group = document.GetElement(self.room_obj.GetParamValueOrDefault(self.group_param))
            if group:
                return RoomGroup(group.Name)
        return RoomGroup("<Без группы>")

    def get_range(self, direction):
        return self.x * direction.X - self.y * direction.Y

    def is_intersect_curve(self, curve_element):
        if not hasattr(self.room_obj, "GetBoundarySegments"):
            return True
        else:
            segments = self.room_obj.GetBoundarySegments(SpatialElementBoundaryOptions())
            segments = [segment for inner_segments in segments
                        for segment in inner_segments]

            for segment in segments:
                curve = segment.GetCurve()

                start = curve.GetEndPoint(0)
                finish = curve.GetEndPoint(1)

                point = curve_element.GeometryCurve.GetEndPoint(0)
                start = XYZ(start.X, start.Y, point.Z)
                finish = XYZ(finish.X, finish.Y, point.Z)

                line = Line.CreateBound(start, finish)
                if line.Intersect(curve_element.GeometryCurve) == SetComparisonResult.Overlap:
                    return True


class RoomGroup(Reactive):
    """
    Class for room groups.
    Methods for comparison groups are overriden for comparison by names.
    """
    def __init__(self, group_name):
        self.name = group_name
        self.__is_checked = True

    @reactive
    def is_checked(self):
        return self.__is_checked

    @is_checked.setter
    def is_checked(self, value):
        self.__is_checked = value

    def __eq__(self, other):
        if not isinstance(other, RoomGroup):
            return NotImplemented

        return self.name == other.name

    def __hash__(self):
        return hash(self.name)


class SelectRoomGroupsWindow(WPFWindow):
    """
    Window for filtering rooms by their group
    """
    def __init__(self, groups):
        self._context = None
        self.xaml_source = op.join(op.dirname(__file__), 'SelectRoomGroupsWindow.xaml')
        super(SelectRoomGroupsWindow, self).__init__(self.xaml_source)

        self.RoomGroups.ItemsSource = groups

    def filter_groups(self, sender, args):
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
            group.is_checked = not group.is_checked


def get_next(enumerable, default):
    return next((e for e in enumerable), default)
