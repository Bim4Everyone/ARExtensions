# -*- coding: utf-8 -*-

from pyrevit import forms
from pyrevit import revit
from pyrevit import EXEC_PARAMS

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI import *
from Autodesk.Revit.Exceptions import *

from dosymep_libs.bim4everyone import log_plugin
from dosymep_libs.simple_services import notification

document = __revit__.ActiveUIDocument.Document


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    links = FilteredElementCollector(document) \
        .WhereElementIsNotElementType() \
        .OfClass(RevitLinkInstance) \
        .ToElements()
    loaded_link_instances = set([link for link in links if RevitLinkType.IsLoaded(document, link.GetTypeId())])
    kr_links = [link for link in loaded_link_instances if "_KR" in link.Name]

    errors = []
    for link_instance in kr_links:
        link_type = document.GetElement(link_instance.GetTypeId())
        is_nested = link_type.IsNestedLink
        if is_nested:
            continue
        model_path = link_type.GetExternalFileReference().GetAbsolutePath()
        is_workshared = link_instance.GetLinkDocument().IsWorkshared

        if (not is_nested) and is_workshared:
            worksets = WorksharingUtils.GetUserWorksetInfo(model_path)
            worksets_to_open = list(filter(lambda workset: not (workset.Name.startswith("КЖ")
                                                                or "29_Скрытые элементы" == workset.Name
                                                                or "28_Конструкции_Вспомогательные" == workset.Name
                                                                or "20_КР_КЖ_Скрыть" == workset.Name
                                                                or "27_Конструкции_Вспомогательные" == workset.Name
                                                                ), worksets))
            workset_ids_to_open = list(map(lambda workset: workset.Id, worksets_to_open))
            workset_configuration = WorksetConfiguration(WorksetConfigurationOption.CloseAllWorksets)
            workset_configuration.Open(workset_ids_to_open)
            try:
                link_type.LoadFrom(model_path, workset_configuration)
            except (ArgumentException,
                    FileAccessException,
                    ForbiddenForDynamicUpdateException,
                    InvalidOperationException) as error:
                errors.append(Element.Name.GetValue(link_type) + "\n-->" + error.Message)
    if errors:
        errors.insert(0, "Следующие связи не обработаны:")
        forms.alert("\n".join(errors), exitscript=True)


script_execute()
