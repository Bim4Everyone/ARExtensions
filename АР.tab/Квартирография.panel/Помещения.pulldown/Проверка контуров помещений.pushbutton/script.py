# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

clr.AddReference("System.Windows.Forms")

from pyrevit.forms import *
from pyrevit import EXEC_PARAMS

from Autodesk.Revit.DB import *

import dosymep

clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.ProjectParams import *

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


class RoomContour:
    def __init__(self, room):
        self.object = room
        self.id = room.Id
        self.name = room.GetParam(BuiltInParameter.ROOM_DEPARTMENT).AsString()
        self.level = room.GetParam(BuiltInParameter.ROOM_LEVEL_ID).AsValueString()
        self.phase = room.GetParam(BuiltInParameter.ROOM_PHASE).AsValueString()

        self.__main_contour = self.__get_contours()[0]
        self.__has_intersection = False

    @property
    def has_intersection(self):
        return self.__find_intersection()

    def __find_intersection(self):
        intersection_result_aray = clr.Reference[IntersectionResultArray]()
        length = len(self.__main_contour)
        for i in range(length-2):
            curve = self.__main_contour[i]
            for j in range(i+2, length):
                if i == 0 and j == length-1:
                    continue

                second_curve = self.__main_contour[j]
                intersect = curve.Intersect(second_curve, intersection_result_aray)

                if intersect == SetComparisonResult.Overlap:
                    return True
        return False

    def __get_contours(self):
        opt = SpatialElementBoundaryOptions()
        boundary_segments_list = self.object.GetBoundarySegments(opt)
        contours = []
        for segment in boundary_segments_list:
            contour = [x.GetCurve() for x in segment]
            contours.append(contour)
        return contours


def get_rooms():
    selection = [doc.GetElement(x) for x in uidoc.Selection.GetElementIds()]
    rooms = [x for x in selection if isinstance(x, Room)]
    if not rooms:
        all_rooms = FilteredElementCollector(doc)
        all_rooms.OfCategory(BuiltInCategory.OST_Rooms).ToElements()
        rooms = [x for x in all_rooms if x.Area > 0]
    return rooms


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    contours = [RoomContour(x) for x in get_rooms()]
    error_rooms = [x for x in contours if x.has_intersection]

    if error_rooms:
        print('Помещение имеет самопересекающийся контур')
        for room in error_rooms:
            try:
                print('{} | {} | {} | {}'.format(room.id, room.name, room.level, room.phase))
            except Exception as e:
                print(e)
    else:
        print('Ошибки не найдены!')


script_execute()
