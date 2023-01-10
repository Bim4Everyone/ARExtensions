# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

from System.Windows.Input import ICommand

clr.AddReference("System.Windows.Forms")

from pyrevit import EXEC_PARAMS

from Autodesk.Revit.DB import *

from pyrevit import *
from pyrevit.forms import *
from pyrevit.revit import *

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.ProjectParams import *
from dosymep.Bim4Everyone.SharedParams import *

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


def freeze_areas(element):
    value = element.GetParam(SharedParamsConfig.Instance.ApartmentLivingArea).AsDouble()
    # element.SetParamValue(SharedParamsConfig.Instance.ApartmentLivingAreaFix, value)
    # #element.LookupParameter("ФОП_ПД_КВ_Приведенная площадь").Set(value)
    #
    # value = element.GetParam(SharedParamsConfig.Instance.ApartmentAreaRatio).AsDouble()
    # element.SetParamValue(SharedParamsConfig.Instance.ApartmentAreaRatioFix, value)
    # #element.LookupParameter("ФОП_ПД_КВ_Приведенная площадь").Set(value)
    #
    # value = element.GetParam(SharedParamsConfig.Instance.ApartmentArea).AsDouble()
    element.SetParamValue(SharedParamsConfig.Instance.ApartmentAreaFix, value)
    # # element.LookupParameter("ФОП_ПД_КВ_Приведенная площадь").Set(value)
    #
    # value = element.GetParam(SharedParamsConfig.Instance.ApartmentAreaNoBalcony).AsDouble()
    # element.SetParamValue(SharedParamsConfig.Instance.ApartmentAreaNoBalconyFix, value)
    # # element.LookupParameter("ФОП_ПД_КВ_Приведенная площадь").Set(value)
    #
    # value = element.GetParam(SharedParamsConfig.Instance.RoomAreaWithRatio).AsDouble()
    # element.SetParamValue(SharedParamsConfig.Instance.RoomAreaWithRatioFix, value)
    # # element.LookupParameter("ФОП_ПД_КВ_Приведенная площадь").Set(value)
    #
    # value = element.GetParam(SharedParamsConfig.Instance.RoomArea).AsDouble()
    # element.SetParamValue(SharedParamsConfig.Instance.RoomAreaFix, value)
    # #element.LookupParameter("ФОП_ПД_КВ_Приведенная площадь").Set(value)

# "ФОП_КВР_Площадь жилая" ProjectParamsConfig.Instance.ApartmentLivingArea
# "ФОП_ФИКС_КВР_Площадь жилая" ProjectParamsConfig.Instance.ApartmentLivingAreaFix

# "ФОП_КВР_Площадь с коэф." ProjectParamsConfig.Instance.ApartmentAreaRatio
# "ФОП_ФИКС_КВР_Площадь с коэф." ProjectParamsConfig.Instance.ApartmentAreaRatioFix

# "ФОП_КВР_Площадь без коэф." ProjectParamsConfig.Instance.ApartmentArea
# "ФОП_ФИКС_КВР_Площадь без коэф." ProjectParamsConfig.Instance.ApartmentAreaFix

# "ФОП_КВР_Площадь без ЛП" ProjectParamsConfig.Instance.ApartmentAreaNoBalcony
# "ФОП_ФИКС_КВР_Площадь без ЛП" ProjectParamsConfig.Instance.ApartmentAreaNoBalconyFix

# "ФОП_КВР_Площадь по пятну" ProjectParamsConfig.Instance.ApartmentFullArea
# "ФОП_ФИКС_КВР_Площадь по пятну" ProjectParamsConfig.Instance.ApartmentFullAreaFix

# "ФОП_ПМЩ_Площадь с коэф." ProjectParamsConfig.Instance.RoomAreaWithRatio
# "ФОП_ФИКС_ПМЩ_Площадь с коэф." ProjectParamsConfig.Instance.RoomAreaWithRatioFix

# "ФОП_ПМЩ_Площадь" ProjectParamsConfig.Instance.RoomArea
# "ФОП_ФИКС_ПМЩ_Площадь" ProjectParamsConfig.Instance.RoomAreaFix

@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    rooms = FilteredElementCollector(doc)
    rooms.OfCategory(BuiltInCategory.OST_Rooms).ToElements()
    with Transaction(doc, "BIM: Заморозить площади помещений") as t:
        t.Start()
        for room in rooms:
            freeze_areas(room)
        t.Commit()


script_execute()
