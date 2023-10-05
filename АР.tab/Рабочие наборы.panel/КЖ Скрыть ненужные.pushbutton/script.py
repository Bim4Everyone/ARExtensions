# -*- coding: utf-8 -*-

from pyrevit import forms
from pyrevit import revit
from pyrevit import EXEC_PARAMS

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *

from dosymep_libs.bim4everyone import log_plugin
from dosymep_libs.simple_services import notification

document = __revit__.ActiveUIDocument.Document


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    links = FilteredElementCollector(document) \
        .WhereElementIsElementType() \
        .OfClass(RevitLinkType) \
        .ToElements()
    loaded_links = [link for link in links if link.IsLoaded(document, link.Id)]
    kr_links = [link for link in loaded_links if "_KR" in Element.Name.GetValue(link)]

    errors = []
    for link in kr_links:
        is_nested = link.IsNestedLink
        if is_nested:
            continue
        model_path = link.GetExternalFileReference().GetAbsolutePath()
        is_workshared = BasicFileInfo.Extract(ModelPathUtils.ConvertModelPathToUserVisiblePath(model_path)).IsWorkshared

        if (not is_nested) and is_workshared:
            worksets = WorksharingUtils.GetUserWorksetInfo(model_path)
            worksets_to_open = list(filter(lambda workset: not (workset.Name.startswith("КЖ")
                                                                or "29_Скрытые элементы" == workset.Name
                                                                or "28_Конструкции_Вспомогательные" == workset.Name
                                                                or "20_КР_КЖ_Скрыть" == workset.Name), worksets))
            workset_ids_to_open = list(map(lambda workset: workset.Id, worksets_to_open))
            workset_configuration = WorksetConfiguration(WorksetConfigurationOption.CloseAllWorksets)
            workset_configuration.Open(workset_ids_to_open)
            try:
                link.LoadFrom(model_path, workset_configuration)
            except (Autodesk.Revit.Exceptions.ArgumentException,
                    Autodesk.Revit.Exceptions.FileAccessException,
                    Autodesk.Revit.Exceptions.ForbiddenForDynamicUpdateException,
                    Autodesk.Revit.Exceptions.InvalidOperationException):
                errors.append(link.Name)
    if errors:
        forms.alert("\n".join(errors), exitscript=True)


script_execute()
