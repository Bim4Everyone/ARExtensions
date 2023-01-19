# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

clr.AddReference("System.Windows.Forms")

from System.Windows.Input import ICommand

import pyevent #pylint: disable=import-error

from pyrevit import *
from pyrevit.forms import *

from Autodesk.Revit.DB import *

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.ProjectParams import *
from dosymep.Bim4Everyone.SharedParams import *
from dosymep.Bim4Everyone.KeySchedules import *
from dosymep.Bim4Everyone.Templates import ProjectParameters

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


def is_float(value):
    try:
        float(value)
        return True
    except:
        return False


class MainWindow(WPFWindow):
    def __init__(self):
        self._context = None
        self.xaml_source = op.join(op.dirname(__file__), 'MainWindow.xaml')
        super(MainWindow, self).__init__(self.xaml_source)

    def ButtonOK_Click(self, sender, e):
        self.DialogResult = True
        show_executed_script_notification()

    def ButtonCancel_Click(self, sender, e):
        self.DialogResult = False
        self.Close()


class MainWindowViewModel(Reactive):
    def __init__(self, schedule_rule, *args):
        Reactive.__init__(self, *args)
        self.__add_new_name = AddNewNameCommand(self)

        self.__room_name = ""
        self.__coefficient = "1"
        self.__is_summer = False
        self.__is_living = False
        self.__error_text = ""
        self.__schedule = find_schedule(doc, schedule_rule.ScheduleName)
        self.__room_department = get_departments_from_schedule(self.__schedule)
        self.__selected_department = ""
        self.__user_input_department = ""

    @property
    def add_new_name(self):
        return self.__add_new_name

    @reactive
    def room_name(self):
        return self.__room_name

    @room_name.setter
    def room_name(self, value):
        self.__room_name = value

    @reactive
    def coefficient(self):
        return self.__coefficient

    @coefficient.setter
    def coefficient(self, value):
        self.__coefficient = value

    @reactive
    def is_summer(self):
        return self.__is_summer

    @is_summer.setter
    def is_summer(self, value):
        self.__is_summer = value

    @reactive
    def is_living(self):
        return self.__is_living

    @is_living.setter
    def is_living(self, value):
        self.__is_living = value

    @reactive
    def room_department(self):
        return self.__room_department

    @room_department.setter
    def room_department(self, value):
        self.__room_department = value

    @reactive
    def selected_department(self):
        return self.__selected_department

    @selected_department.setter
    def selected_department(self, value):
        self.__selected_department = value

    @reactive
    def user_input_department(self):
        return self.__user_input_department

    @user_input_department.setter
    def user_input_department(self, value):
        self.__user_input_department = value
        self.__room_department.Add(self.__user_input_department)
        self.__selected_department = self.__user_input_department

    @reactive
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value

    @reactive
    def schedule(self):
        return self.__schedule


class AddNewNameCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model
        self.__view_model.PropertyChanged += self.ViewModel_PropertyChanged

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def ViewModel_PropertyChanged(self, sender, e):
        self.OnCanExecuteChanged()

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def CanExecute(self, parameter):
        if not self.__view_model.room_name or not self.__view_model.coefficient:
            self.__view_model.error_text = "Заполните все поля."
            return False

        if not is_float(self.__view_model.coefficient):
            self.__view_model.error_text = "Коэффициент должен быть числом."
            return False

        self.__view_model.error_text = None
        return True

    def Execute(self, parameter):
        names_schedule = self.__view_model.schedule
        table_data = names_schedule.GetTableData()
        section_data = table_data.GetSectionData(SectionType.Body)

        keys_before = get_keys_from_schedule(names_schedule)

        with revit.Transaction("BIM: Добавить новое наименование помещения"):
            section_data.InsertRow(section_data.FirstRowNumber)

            keys_after = get_keys_from_schedule(names_schedule)
            new_key_id = [x for x in keys_after if x not in keys_before][0]
            new_key = doc.GetElement(ElementId(new_key_id))

            new_key.SetParamValue(BuiltInParameter.REF_TABLE_ELEM_NAME, self.__view_model.room_name)
            new_key.SetParamValue(BuiltInParameter.ROOM_DEPARTMENT, self.__view_model.selected_department)
            new_key.SetParamValue(BuiltInParameter.ROOM_NAME, self.__view_model.room_name)
            new_key.SetParamValue(SharedParamsConfig.Instance.RoomAreaRatio, float(self.__view_model.coefficient))
            new_key.SetParamValue(ProjectParamsConfig.Instance.IsRoomBalcony, self.__view_model.is_summer)
            new_key.SetParamValue(ProjectParamsConfig.Instance.IsRoomLiving, self.__view_model.is_living)

        return True


def find_schedule(document, name):
    schedules = FilteredElementCollector(document).OfClass(ViewSchedule)

    fvp = ParameterValueProvider(ElementId(BuiltInParameter.VIEW_NAME))
    rule = FilterStringEquals()
    value = name
    case_sens = False
    filter_rule = FilterStringRule(fvp, rule, value, case_sens)
    name_filter = ElementParameterFilter(filter_rule)

    schedules.WherePasses(name_filter)
    return schedules.FirstElement()


def get_keys_from_schedule(schedule):
    elements = FilteredElementCollector(schedule.Document, schedule.Id).ToElements()
    keys = [x.Id.IntegerValue for x in elements]
    return keys


def get_departments_from_schedule(schedule):
    elements = FilteredElementCollector(schedule.Document, schedule.Id).ToElements()
    departments = {x.GetParamValueOrDefault(BuiltInParameter.ROOM_DEPARTMENT) for x in elements}
    return ObservableCollection[str](departments)


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    script_start = True
    name_schedule = KeySchedulesConfig.Instance.RoomsNames
    ProjectParameters.Create(doc.Application).SetupSchedule(doc, False, name_schedule)

    while script_start:
        main_window = MainWindow()
        main_window.DataContext = MainWindowViewModel(name_schedule)
        main_window.show_dialog()
        script_start = main_window.DialogResult
        if not script_start:
            script.exit()


script_execute()
