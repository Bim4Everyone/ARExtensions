# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

clr.AddReference("System.Windows.Forms")
from System.Windows.Forms import MessageBox

from System.Windows.Input import ICommand

import pyevent #pylint: disable=import-error

from pyrevit import *
from pyrevit.forms import *
from pyrevit.revit import *

from Autodesk.Revit.DB import *

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.ProjectParams import *
from dosymep.Bim4Everyone.KeySchedules import *

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


class MainWindowViewModel(Reactive):
    def __init__(self, *args):
        Reactive.__init__(self, *args)
        self.__add_new_name = AddNewNameCommand(self)

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
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value


class AddNewNameCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model
        self.__view_model.PropertyChanged += self.ViewModel_PropertyChanged

        self.__view_model.room_name = ""
        self.__view_model.coefficient = "1"
        self.__view_model.is_summer = False
        self.__view_model.is_living = False
        self.__error_text = ""

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
        names_schedule = find_schedule(doc, KeySchedulesConfig.Instance.RoomsNames.ScheduleName)
        table_data = names_schedule.GetTableData()
        section_data = table_data.GetSectionData(SectionType.Body)

        keys_before = get_keys_from_schedule(names_schedule)

        with Transaction(doc, "BIM: Добавить новое наименование помещения") as t:

            t.Start()
            section_data.InsertRow(section_data.FirstRowNumber)

            keys_after = get_keys_from_schedule(names_schedule)
            new_key_id = [x for x in keys_after if x not in keys_before][0]
            new_key = doc.GetElement(ElementId(new_key_id))

            new_key.SetParamValue(BuiltInParameter.REF_TABLE_ELEM_NAME, self.__view_model.room_name)
            new_key.SetParamValue(BuiltInParameter.ROOM_NAME, self.__view_model.room_name)
            new_key.LookupParameter("ФОП_Коэффициент площади").Set(float(self.__view_model.coefficient))
            #new_key.SetParamValue(ProjectParamsConfig.Instance.RoomAreaRatio, self.__view_model.coefficient)
            new_key.SetParamValue(ProjectParamsConfig.Instance.IsRoomBalcony, self.__view_model.is_summer)
            new_key.SetParamValue(ProjectParamsConfig.Instance.IsRoomLiving, self.__view_model.is_living)

            t.Commit()

        return True


def find_schedule(doc, name):
    schedules = FilteredElementCollector(doc).OfClass(ViewSchedule)

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


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    main_window = MainWindow()
    main_window.DataContext = MainWindowViewModel()



    if not main_window.show_dialog():
        script.exit()


script_execute()
