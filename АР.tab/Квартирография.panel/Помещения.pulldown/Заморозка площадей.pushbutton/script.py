# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

from System import Guid

clr.AddReference("System.Windows.Forms")

from pyrevit import EXEC_PARAMS

from Autodesk.Revit.DB import *

from pyrevit import *
from pyrevit.revit import *

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.SharedParams import *

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


def freeze_area(element, param, guid_str):
    value = element.GetParam(param).AsDouble()
    guid = Guid(guid_str)
    element.SetParamValue(element.get_Parameter(guid).Definition.Name, value)


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    rooms = FilteredElementCollector(doc)
    rooms.OfCategory(BuiltInCategory.OST_Rooms).ToElements()
    with Transaction(doc, "BIM: Заморозить площади помещений") as t:
        t.Start()
        for room in rooms:
            freeze_area(room, SharedParamsConfig.Instance.ApartmentLivingArea, '421ec146-2f9b-48ae-9bcc-1f478c115e7e')
            freeze_area(room, SharedParamsConfig.Instance.ApartmentAreaRatio, '77713404-35ef-4c8a-a5c4-c6f3d4da16c2')
            freeze_area(room, SharedParamsConfig.Instance.ApartmentArea, '3d6c5084-d6ab-490e-baa6-f8d119a0d628')
            freeze_area(room, SharedParamsConfig.Instance.ApartmentAreaNoBalcony, '8226f116-c19e-4797-a3bb-55ac79acdf44')
            # freeze_area(room, SharedParamsConfig.Instance.ApartmentFullAreaFix, 'bc1bf705-37a8-404e-af7c-ca072168b994')
            freeze_area(room, SharedParamsConfig.Instance.RoomAreaWithRatio, '46bc1213-6d5a-4164-84d0-598a9abcf70d')
            freeze_area(room, SharedParamsConfig.Instance.RoomArea, '64bf4d4d-6ef3-4cfd-b452-eccdde94a8ad')
        t.Commit()


script_execute()
