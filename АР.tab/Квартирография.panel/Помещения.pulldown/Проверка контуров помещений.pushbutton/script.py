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



@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    pass


script_execute()
