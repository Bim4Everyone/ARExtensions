# -*- coding: utf-8 -*-
import clr
import datetime

from System.Collections.Generic import *

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

from System.Windows.Input import ICommand

import pyevent
from pyrevit import EXEC_PARAMS, revit
from pyrevit.forms import *
from pyrevit import script

from Autodesk.Revit.DB import *
from Autodesk.Revit.UI.Selection import *

import dosymep

clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *


doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
app = doc.Application

class RevitRepository:
    """
    This class created for collecting, checking and filtering elements from revit document.
    The class collects all elements of required categories.
    The class has methods to check availability of parameters and their values.
    The class has methods to filter elements by rules and table type.
    """

    def __init__(self, doc):
        self.doc = doc

        self.__selected_views = self.__get_selected_views()
        self.__volume_of_interest_items = self.__get_volume_of_interest_items()
        self.__view_templates = self.__get_view_templates()

    @reactive
    def selected_views(self):
        return self.__selected_views

    @reactive
    def volume_of_interest_items(self):
        return self.__volume_of_interest_items

    @reactive
    def view_templates(self):
        return self.__view_templates

    def __get_volume_of_interest_items(self):
        volumes_of_interest = FilteredElementCollector(self.doc).OfCategory(BuiltInCategory.OST_VolumeOfInterest) \
            .WhereElementIsNotElementType().ToElements()
        if 0 == volumes_of_interest.Count:
            alert("В проекте не найдено ни одной области видимости")
            script.exit()

        volume_of_interest_items = [VolumesOfInterestItem(volume) for volume in volumes_of_interest]

        return volume_of_interest_items

    def __get_view_templates(self):
        views = FilteredElementCollector(self.doc).OfClass(ViewPlan) \
            .WhereElementIsNotElementType().ToElements()
        view_templates = [view for view in views if view.IsTemplate]
        if view_templates.Count == 0:
            alert("В проекте не найдено ни одного шаблона вида")
            script.exit()

        return view_templates

    @staticmethod
    def __get_selected_views():
        views = []
        selected_ids = uidoc.Selection.GetElementIds()

        if 0 == selected_ids.Count:
            alert("В проекте не выбран ни один вид")
            script.exit()

        for id in selected_ids:
            elem = doc.GetElement(id)
            if isinstance(elem, ViewPlan):
                views.append(elem)

        if 0 == views.Count:
            alert("Ни один выбранный вид не является видом в плане")
            script.exit()
        return views


class VolumesOfInterestItem:
    def __init__(self, volumes_of_interest):
        self.__volumes_of_interest = volumes_of_interest
        self.__is_checked = False

    @reactive
    def volumes_of_interest(self):
        return self.__volumes_of_interest

    @volumes_of_interest.setter
    def volumes_of_interest(self, value):
        self.__volumes_of_interest = value

    @reactive
    def is_checked(self):
        return self.__is_checked

    @is_checked.setter
    def is_checked(self, value):
        self.__is_checked = value


class CreateViewsCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model
        self.__view_model.PropertyChanged += self.ViewModel_PropertyChanged

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        # В Python при работе с событиями нужно явно
        # передавать импорт в обработчике события
        from System import EventArgs
        self._canExecuteChanged(self, EventArgs.Empty)

    def ViewModel_PropertyChanged(self, sender, e):
        self.OnCanExecuteChanged()

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):

        filter_1 = self.__view_model.view_name_filter_1
        filter_2 = self.__view_model.view_name_filter_2

        with ((revit.Transaction("BIM: Создание таблицы УПК"))):
            for view in self.__view_model.revit_repository.selected_views:

                if len(filter_1) > 0 and filter_1 not in view.Name:
                    # alert(view.Name, "Не прошел по фильтру 1")
                    continue
                if len(filter_2) > 0 and filter_2 not in view.Name:
                    # alert(view.Name, "Не прошел по фильтру 2")
                    continue

                for volume_of_interest_item in self.__view_model.volume_of_interest_items:
                    if not volume_of_interest_item.is_checked:
                        continue

                    new_view_id = view.Duplicate(ViewDuplicateOption.WithDetailing)
                    new_view = doc.GetElement(new_view_id)

                    if self.__view_model.selected_view_template is not None:
                        new_view.ViewTemplateId = self.__view_model.selected_view_template.Id

                    volumes_of_interest = volume_of_interest_item.volumes_of_interest
                    new_view_volume_of_interest_param = new_view.get_Parameter(BuiltInParameter.VIEWER_VOLUME_OF_INTEREST_CROP)
                    if not new_view_volume_of_interest_param.IsReadOnly:
                        new_view.get_Parameter(BuiltInParameter.VIEWER_VOLUME_OF_INTEREST_CROP).Set(volumes_of_interest.Id)

                    level_name = new_view.GenLevel.Name
                    for name_part in level_name.split("_"):
                        if "этаж" in name_part:
                            # name_part = name_part.replace("этаж", "")
                            # name_part = name_part.replace(" ", "")
                            level_number = "".join(c for c in name_part if c.isdecimal())
                            break

                    if self.__view_model.are_above_ground_elements:
                        new_view.Name = self.__view_model.name_prefix \
                                        + volumes_of_interest.Name + "_" + level_number \
                                        + self.__view_model.name_suffix
                    else:
                        new_view.Name = self.__view_model.name_prefix \
                                        + level_number + "_" + volumes_of_interest.Name \
                                        + self.__view_model.name_suffix
        return True


class CheckAllVolumesOfInterestCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model
        self.__view_model.PropertyChanged += self.ViewModel_PropertyChanged

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        # В Python при работе с событиями нужно явно
        # передавать импорт в обработчике события
        from System import EventArgs
        self._canExecuteChanged(self, EventArgs.Empty)

    def ViewModel_PropertyChanged(self, sender, e):
        self.OnCanExecuteChanged()

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):

        #temp = []
        for volume_of_interest_item in self.__view_model.volume_of_interest_items:
            if not self.__view_model.check_status:
                volume_of_interest_item.is_checked = True

            else:
                volume_of_interest_item.is_checked = False
            #temp.append(volume_of_interest_item)

        self.__view_model.OnPropertyChanged("volume_of_interest_items")
        self.__view_model.OnPropertyChanged("__volume_of_interest_items")
        self.__view_model.check_status = not self.__view_model.check_status

        #self.__view_model.volume_of_interest_items = []
        #self.__view_model.volume_of_interest_items = temp
        return True


class MainWindow(WPFWindow):
    def __init__(self):
        self._context = None
        self.xaml_source = op.join(op.dirname(__file__), "MainWindow.xaml")
        super(MainWindow, self).__init__(self.xaml_source)

    def ButtonOK_Click(self, sender, e):
        self.DialogResult = True

    def ButtonCancel_Click(self, sender, e):
        self.DialogResult = False
        self.Close()


class MainWindowViewModel(Reactive):
    def __init__(self, revit_repository):
        Reactive.__init__(self)
        self.__revit_repository = revit_repository
        self.__view_templates = revit_repository.view_templates
        if len(self.__view_templates) > 0:
            self.__selected_view_template = self.__view_templates[0]

        self.__volume_of_interest_items = revit_repository.volume_of_interest_items

        self.__view_name_filter_1 = "ПСО_"
        self.__view_name_filter_2 = ""
        self.__are_above_ground_elements = True
        self.__name_prefix = "ШИФР_дом 1_"
        self.__name_suffix = ""

        self.__check_status = False
        self.__error_text = ""
        self.__create_views_command = CreateViewsCommand(self)
        self.__check_all_volumes_of_interest_command = CheckAllVolumesOfInterestCommand(self)

    @reactive
    def revit_repository(self):
        return self.__revit_repository

    @reactive
    def view_name_filter_1(self):
        return self.__view_name_filter_1

    @view_name_filter_1.setter
    def view_name_filter_1(self, value):
        self.__view_name_filter_1 = value

    @reactive
    def view_name_filter_2(self):
        return self.__view_name_filter_2

    @view_name_filter_2.setter
    def view_name_filter_2(self, value):
        self.__view_name_filter_2 = value

    @reactive
    def volume_of_interest_items(self):
        return self.__volume_of_interest_items

    @volume_of_interest_items.setter
    def volume_of_interest_items(self, value):
        self.__volume_of_interest_items = value

    @reactive
    def are_above_ground_elements(self):
        return self.__are_above_ground_elements

    @are_above_ground_elements.setter
    def are_above_ground_elements(self, value):
        self.__are_above_ground_elements = value

    @reactive
    def view_templates(self):
        return self.__view_templates

    @reactive
    def selected_view_template(self):
        return self.__selected_view_template

    @selected_view_template.setter
    def selected_view_template(self, value):
        self.__selected_view_template = value

    @reactive
    def name_prefix(self):
        return self.__name_prefix

    @name_prefix.setter
    def name_prefix(self, value):
        self.__name_prefix = value

    @reactive
    def name_suffix(self):
        return self.__name_suffix

    @name_suffix.setter
    def name_suffix(self, value):
        self.__name_suffix = value

    @reactive
    def check_status(self):
        return self.__check_status

    @check_status.setter
    def check_status(self, value):
        self.__check_status = value

    @reactive
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value

    @property
    def create_views_command(self):
        return self.__create_views_command

    @property
    def check_all_volumes_of_interest_command(self):
        return self.__check_all_volumes_of_interest_command


def convert_value(parameter):
    if parameter.StorageType == StorageType.Double:
        value = parameter.AsDouble()
    if parameter.StorageType == StorageType.Integer:
        value = parameter.AsInteger()
    if parameter.StorageType == StorageType.String:
        value = parameter.AsString()
    if parameter.StorageType == StorageType.ElementId:
        value = parameter.AsValueString()

    if int(app.VersionNumber) > 2021:
        d_type = parameter.GetUnitTypeId()
        result = UnitUtils.ConvertFromInternalUnits(value, d_type)
    else:
        d_type = parameter.DisplayUnitType
        result = UnitUtils.ConvertFromInternalUnits(value, d_type)
    return result


def convert_length(value):
    if int(app.VersionNumber) < 2021:
        unit_type = DisplayUnitType.DUT_MILLIMETERS
    else:
        unit_type = UnitTypeId.Millimeters
    converted_value = UnitUtils.ConvertToInternalUnits(value, unit_type)
    return converted_value


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    revit_repository = RevitRepository(doc)

    # views = revit_repository.selected_views

    main_window = MainWindow()
    main_window.DataContext = MainWindowViewModel(revit_repository)
    main_window.show_dialog()
    if not main_window.DialogResult:
        script.exit()


script_execute()
