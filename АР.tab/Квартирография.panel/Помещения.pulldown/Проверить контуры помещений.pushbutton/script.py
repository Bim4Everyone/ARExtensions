# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

from pyrevit.forms import *
from pyrevit import EXEC_PARAMS

from Autodesk.Revit.DB.Architecture import Room
from Autodesk.Revit.DB import *

import dosymep

clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep.Revit import SpatialElementExtensions
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
        return SpatialElementExtensions.IsSelfCrossBoundaries(self.object)

    def __get_contours(self):
        opt = SpatialElementBoundaryOptions()
        boundary_segments_list = self.object.GetBoundarySegments(opt)
        contours = []
        for segment in boundary_segments_list:
            contour = [x.GetCurve() for x in segment]
            contours.append(contour)
        return contours


def get_all_docs():
    links = FilteredElementCollector(doc).OfClass(RevitLinkInstance)
    not_nested_links = [x for x in links if not doc.GetElement(x.GetTypeId()).IsNestedLink]
    links_doc = [x.GetLinkDocument() for x in not_nested_links if x.GetLinkDocument()]
    links_doc.insert(0, doc)

    return links_doc


def get_rooms():
    rooms = revit.get_selection().include(Room).elements
    if not rooms:
        docs = get_all_docs()
        for document in docs:
            doc_rooms = FilteredElementCollector(document).OfCategory(BuiltInCategory.OST_Rooms)
            rooms += [x for x in doc_rooms if x.Area > 0]
    return rooms


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    errors = []
    contours = [RoomContour(x) for x in get_rooms()]

    for room in contours:
        if room.has_intersection:
            errors.append([room.id,
                           room.name,
                           room.level,
                           room.phase,
                           room.document])

    if errors:
        output = script.get_output()
        output.print_table(table_data=errors,
                           title="Помещения с самопересекающимся контуром",
                           columns=["Id", "Имя", "Уровень", "Стадия", "Файл"])
    else:
        alert('Ошибки не найдены!')


script_execute()
