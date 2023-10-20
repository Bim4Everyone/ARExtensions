# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

from System import Guid

from pyrevit import EXEC_PARAMS, revit

from Autodesk.Revit.DB import *

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.SharedParams import *
from dosymep.Bim4Everyone.Templates import ProjectParameters

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    area_params = [SharedParamsConfig.Instance.ApartmentLivingArea,
                   SharedParamsConfig.Instance.ApartmentAreaRatio,
                   SharedParamsConfig.Instance.ApartmentArea,
                   SharedParamsConfig.Instance.ApartmentAreaNoBalcony,
                   SharedParamsConfig.Instance.ApartmentFullArea,
                   SharedParamsConfig.Instance.RoomAreaWithRatio,
                   SharedParamsConfig.Instance.RoomArea]

    area_fix_params = [SharedParamsConfig.Instance.ApartmentLivingAreaFix,
                       SharedParamsConfig.Instance.ApartmentAreaRatioFix,
                       SharedParamsConfig.Instance.ApartmentAreaFix,
                       SharedParamsConfig.Instance.ApartmentAreaNoBalconyFix,
                       SharedParamsConfig.Instance.ApartmentFullAreaFix,
                       SharedParamsConfig.Instance.RoomAreaWithRatioFix,
                       SharedParamsConfig.Instance.RoomAreaFix]

    rooms = FilteredElementCollector(doc)
    rooms.OfCategory(BuiltInCategory.OST_Rooms).ToElements()

    if rooms.FirstElement():
        for param in area_params:
            if not rooms.FirstElement().IsExistsParam(param):
                ProjectParameters.Create(doc.Application).SetupRevitParam(doc, param)

        for param in area_fix_params:
            if not rooms.FirstElement().IsExistsParam(param):
                ProjectParameters.Create(doc.Application).SetupRevitParam(doc, param)

        with revit.Transaction("BIM: Заморозить площади помещений"):
            for room in rooms:
                for param, param_fix in zip(area_params, area_fix_params):
                    room.SetParamValue(param_fix, param)


script_execute()
