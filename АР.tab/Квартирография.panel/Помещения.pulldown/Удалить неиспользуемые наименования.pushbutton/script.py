# -*- coding: utf-8 -*-
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

from System.Windows.Input import ICommand

from Autodesk.Revit.DB import *

from pyrevit import *
from pyrevit.forms import *
from pyrevit.revit import *

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep_libs.bim4everyone import *
from dosymep.Bim4Everyone.ProjectParams import *
from dosymep.Bim4Everyone.KeySchedules import *
from dosymep.Bim4Everyone.Templates import ProjectParameters

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


class InvertCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):
        for name in self.__view_model.names:
            name.is_checked = not name.is_checked


class UpdateStatesCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, value, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model
        self.__value = value

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):
        for name in self.__view_model.names:
            name.is_checked = self.__value


class DeleteKeyCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model
        self.__view_model.PropertyChanged += self.ViewModel_PropertyChanged

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
        names_to_delete = [x for x in self.__view_model.names if x.is_checked]
        if not names_to_delete:
            self.__view_model.error_text = "Необходимо выбрать наименования."
            return False

        self.__view_model.error_text = None
        return True

    def Execute(self, parameter):
        with revit.Transaction("BIM: Удалить неиспользуемые наименования"):
            for name in self.__view_model.names:
                if name.is_checked:
                    doc.Delete(name.key_object.Id)


class MainWindow(WPFWindow):
    def __init__(self):
        self._context = None
        self.xaml_source = op.join(op.dirname(__file__), 'MainWindow.xaml')
        super(MainWindow, self).__init__(self.xaml_source)

    def button_ok_click(self, sender, e):
        self.DialogResult = True
        self.Close()

    def ButtonCancel_Click(self, sender, e):
        self.DialogResult = False
        self.Close()


class MainWindowViewModel(Reactive):
    def __init__(self, names, *args):
        Reactive.__init__(self, *args)
        self.__names = names
        self.__delete_names = DeleteKeyCommand(self)
        self.__invert_states = InvertCommand(self)
        self.__set_all_true = UpdateStatesCommand(self, True)
        self.__set_all_false = UpdateStatesCommand(self, False)
        self.__error_text = ""

    @property
    def delete_names(self):
        return self.__delete_names

    @property
    def invert_states(self):
        return self.__invert_states

    @property
    def set_all_true(self):
        return self.__set_all_true

    @property
    def set_all_false(self):
        return self.__set_all_false

    @reactive
    def names(self):
        return self.__names

    @names.setter
    def names(self, value):
        self.__names = value

    @reactive
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value


class KeyRoomName(Reactive):
    def __init__(self, key_object):
        self.key_object = key_object
        self.__name = key_object.GetParamValueOrDefault(BuiltInParameter.ROOM_NAME)
        self.__department = key_object.GetParamValueOrDefault(BuiltInParameter.ROOM_DEPARTMENT)
        self.__is_checked = False

    @reactive
    def name(self):
        return self.__name

    @name.setter
    def name(self, value):
        self.__name = value

    @reactive
    def department(self):
        return self.__department

    @department.setter
    def department(self, value):
        self.__department = value

    @reactive
    def is_checked(self):
        return self.__is_checked

    @is_checked.setter
    def is_checked(self, value):
        self.__is_checked = value


def find_schedule(document, name):
    schedules = FilteredElementCollector(document).OfClass(ViewSchedule)

    fvp = ParameterValueProvider(ElementId(BuiltInParameter.VIEW_NAME))
    rule = FilterStringEquals()
    value = name
    filter_rule = FilterStringRule(fvp, rule, value)
    name_filter = ElementParameterFilter(filter_rule)

    schedules.WherePasses(name_filter)
    return schedules.FirstElement()


def get_unused_room_names(schedule_rule):
    rooms = FilteredElementCollector(doc)
    rooms.OfCategory(BuiltInCategory.OST_Rooms).ToElements()
    room_names = {x.GetParamValueOrDefault(BuiltInParameter.ROOM_NAME) for x in rooms}

    schedule = find_schedule(doc, schedule_rule.ScheduleName)
    all_keys = FilteredElementCollector(schedule.Document, schedule.Id).ToElements()
    key_names = [KeyRoomName(x) for x in all_keys]

    unused_names = [x for x in key_names if x.name not in room_names]
    unused_names = sorted(unused_names, key=lambda x: x.name)
    return unused_names


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    name_schedule = KeySchedulesConfig.Instance.RoomsNames
    ProjectParameters.Create(doc.Application).SetupSchedule(doc, False, name_schedule)
    unused_names = get_unused_room_names(name_schedule)

    main_window = MainWindow()
    main_window.DataContext = MainWindowViewModel(unused_names)
    if not main_window.show_dialog():
        script.exit()


script_execute()
