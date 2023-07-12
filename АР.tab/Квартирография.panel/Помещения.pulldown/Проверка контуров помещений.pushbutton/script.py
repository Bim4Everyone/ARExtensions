# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

from pyrevit.forms import *
from pyrevit import EXEC_PARAMS
from pyrevit import script

from Autodesk.Revit.DB.Architecture import Room
from Autodesk.Revit.DB import *

import dosymep

clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


class RoomContour:
    def __init__(self, room):
        self.object = room
        self.id = room.Id
        self.name = room.GetParam(BuiltInParameter.ROOM_NAME).AsString()
        self.level = room.GetParam(BuiltInParameter.ROOM_LEVEL_ID).AsValueString()
        self.phase = room.GetParam(BuiltInParameter.ROOM_PHASE).AsValueString()
        self.document = room.Document.Title

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


def get_all_docs():
    links_doc = [doc]
    links = FilteredElementCollector(doc).OfClass(RevitLinkInstance)
    not_nested_links = [x for x in links if not doc.GetElement(x.GetTypeId()).IsNestedLink]

    for link in not_nested_links:
        link_doc = link.GetLinkDocument()
        if link_doc:
            links_doc.append(link_doc)

    return links_doc


def get_rooms():
    selection = [doc.GetElement(x) for x in uidoc.Selection.GetElementIds()]
    rooms = [x for x in selection if isinstance(x, Room)]
    if not rooms:
        docs = get_all_docs()
        for document in docs:
            doc_rooms = FilteredElementCollector(document)
            doc_rooms.OfCategory(BuiltInCategory.OST_Rooms).ToElements()
            rooms += [x for x in doc_rooms if x.Area > 0]
    return rooms


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    errors = []
    contours = [RoomContour(x) for x in get_rooms()]

    for room in contours:
        if room.has_intersection:
            room_error = []
            room_error.append(room.id)
            room_error.append(room.name)
            room_error.append(room.level)
            room_error.append(room.phase)
            room_error.append(room.document)
            errors.append(room_error)

    if errors:
        output = script.get_output()
        output.print_table(table_data=errors,
                           title="Помещения с самопересекающимся контуром",
                           columns=["Id", "Имя", "Уровень", "Стадия", "Файл"])
    else:
        alert('Ошибки не найдены!')


script_execute()
