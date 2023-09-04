# coding=utf-8
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import math
import os.path as op
import pyevent  # pylint: disable=import-error

import System
from System.Diagnostics import Stopwatch
from System.Windows.Input import ICommand
from Autodesk.Revit.DB import *

from pyrevit import forms
from pyrevit import EXEC_PARAMS
from pyrevit import revit
from pyrevit.forms import Reactive, reactive
from pyrevit.revit import selection, HOST_APP

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep.Bim4Everyone.SharedParams import *
from dosymep.Bim4Everyone.SystemParams import *
from dosymep.Bim4Everyone.ProjectParams import *

from dosymep_libs.bim4everyone import *

log_debug = False
log_point_debug = False
log_elapsed_time_debug = False

text_debug = False
circle_debug = False

eps = 1.0e-9
document = __revit__.ActiveUIDocument.Document  # type: Document


class RevitRepository:
    def __init__(self, document, ui_application):
        self.__document = document
        self.__application = ui_application

        self.__elements = [element for element in selection.get_selection().elements
            if element.LevelId == document.ActiveView.GenLevel.Id]

        self.__room_elements = self.get_elements(BuiltInCategory.OST_Rooms)

    @property
    def is_empty(self):
        return not self.__room_elements

    def get_phases(self):
        return set(sorted((self.get_phase(element) for element in self.__room_elements)))

    def get_params(self):
        element = get_next(self.__room_elements, None)
        if element:
            return set(sorted((param.Definition.Name for param in element.Parameters if param.StorageType == StorageType.String)))
        return set()

    def get_elements(self, category):
        category = Category.GetCategory(self.__document, category)
        return [element for element in self.__elements if element.Category.Id == category.Id]

    def get_rooms(self):
        return self.__room_elements

    def get_default_param(self):
        return LabelUtils.GetLabelFor(BuiltInParameter.ROOM_NUMBER)

    @staticmethod
    def get_phase(element):
        return element.GetParam(BuiltInParameter.ROOM_PHASE).AsValueString()

    @staticmethod
    def pick_element(title):
        with forms.WarningBar(title=title):
            return selection.pick_element(title)


def get_next(enumerable, default):
    return next((e for e in enumerable), default)


def filter_groups():
    pass