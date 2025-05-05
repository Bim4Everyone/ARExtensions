# coding=utf-8
import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import math
import pyevent  # pylint: disable=import-error

import System
from System.Diagnostics import Stopwatch
from System.Windows.Input import ICommand
from Autodesk.Revit.DB import *

from pyrevit.forms import *
from pyrevit import EXEC_PARAMS
from pyrevit import revit
from pyrevit.revit import selection, HOST_APP

import dosymep
clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from dosymep.Bim4Everyone.ProjectParams import *
from dosymep_libs.bim4everyone import *

from rooms import *

log_debug = False
log_point_debug = False
log_elapsed_time_debug = False

text_debug = False
circle_debug = False

eps = 1.0e-9
document = __revit__.ActiveUIDocument.Document  # type: Document


def log_information(message):
    if log_debug:
        print message


def log_point(message):
    if log_point_debug:
        print message


def log_elapsed_time(message):
    if log_elapsed_time_debug:
        print message


def is_int(value):
    try:
        int(value)
        return True
    except:
        return False


def create_text(text, location):
    if text_debug:
        options = TextNoteOptions()
        options.Rotation = 0
        options.TypeId = FilteredElementCollector(document).OfClass(TextNoteType).FirstElementId()
        options.VerticalAlignment = VerticalTextAlignment.Middle
        options.HorizontalAlignment = HorizontalTextAlignment.Center

        return TextNote.Create(document, document.ActiveView.Id, location, str(text), options)


def create_circle(radius, location):
    if circle_debug:
        plane = Plane.CreateByNormalAndOrigin(XYZ.BasisZ, location)
        arc = Arc.Create(plane, radius, 0, 2 * math.pi)

        return document.Create.NewDetailCurve(document.ActiveView, arc)


def convert_value(value):
    if HOST_APP.is_older_than(2022):
        return UnitUtils.ConvertToInternalUnits(value, DisplayUnitType.DUT_MILLIMETERS)
    else:
        return UnitUtils.ConvertToInternalUnits(value, UnitTypeId.Millimeters)


def get_index_points(curve):
    step_size = convert_value(500)
    log_point("step_size: {}".format(step_size))

    create_circle(0.5, curve.GetEndPoint(0))
    log_point("left_point: {}".format(curve.GetEndPoint(0)))

    create_circle(0.5, curve.GetEndPoint(1))
    log_point("right_point: {}".format(curve.GetEndPoint(1)))

    points = curve.Tessellate()
    current_point = curve.GetEndPoint(0)

    index = 0
    create_text(index, current_point)

    for point in points:
        distance = point.DistanceTo(current_point)
        if distance >= step_size:
            count_points = int(distance / step_size)

            log_point("distance: {}".format(distance))
            log_point("count_points: {}".format(count_points))

            x = current_point.X
            y = current_point.Y
            z = current_point.Z

            x_offset = (point.X - x) / count_points
            y_offset = (point.Y - y) / count_points

            for i in range(count_points):
                x = current_point.X + x_offset
                y = current_point.Y + y_offset

                log_point("point: {}".format(point))
                log_point("current_point: {}".format(current_point))
                log_point("new_point: {}".format(XYZ(x, y, 0)))

                point = XYZ(x, y, z)
                current_point = point
                create_circle(0.5, current_point)

                index += 1
                create_text(index, current_point)

                yield current_point
            continue

    index += 1
    create_text(index, curve.GetEndPoint(1))


class MainWindow(WPFWindow):
    def __init__(self, ):
        self._context = None
        self.xaml_source = op.join(op.dirname(__file__), 'MainWindow.xaml')
        super(MainWindow, self).__init__(self.xaml_source)
        self.Loaded += self.MainWindow_Loaded

    def ButtonOK_Click(self, sender, e):
        self.DialogResult = True
        self.Close()

    def ButtonCancel_Click(self, sender, e):
        self.DialogResult = False
        self.Close()

    def MainWindow_Loaded(self, sender, event):
        self.MinHeight = self.Height


class MainWindowViewModel(Reactive):
    def __init__(self, revit_repository, view, *args):
        Reactive.__init__(self, *args)

        self.__curve = None
        self.__selected_elem_name = None
        self.__revit_repository = revit_repository

        self.start_number = "1"

        self.__prefix = ""
        self.__suffix = ""

        self.__error_text = ""

        self.__numerate_command = NumerateRoomsCommand(self, self.__revit_repository)
        self.__select_line_command = SelectLineCommand(view, self, self.__revit_repository)

        self.__param_names = []
        self.__param_name = None

        self.param_name = self.__revit_repository.get_default_param()
        self.param_names = self.__revit_repository.get_params()

    @property
    def curve_element(self):
        return self.__curve

    @curve_element.setter
    def curve_element(self, value):
        self.__curve = value
        self.selected_elem_name = "{} ({})".format(str(self.__curve.Id.IntegerValue), self.__curve.Category.Name) if self.__curve else None

    @reactive
    def selected_elem_name(self):
        return self.__selected_elem_name

    @selected_elem_name.setter
    def selected_elem_name(self, value):
        self.__selected_elem_name = value

    @reactive
    def start_number(self):
        return self.__start_number

    @start_number.setter
    def start_number(self, value):
        self.__start_number = value

    @reactive
    def prefix(self):
        return self.__prefix

    @prefix.setter
    def prefix(self, value):
        self.__prefix = value

    @reactive
    def suffix(self):
        return self.__suffix

    @suffix.setter
    def suffix(self, value):
        self.__suffix = value

    @reactive
    def param_names(self):
        return self.__param_names

    @param_names.setter
    def param_names(self, value):
        self.__param_names = value

    @reactive
    def param_name(self):
        return self.__param_name

    @param_name.setter
    def param_name(self, value):
        self.__param_name = value

    @reactive
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value

    @property
    def numerate_command(self):
        return self.__numerate_command

    @property
    def select_line_command(self):
        return self.__select_line_command


class NumerateRoomsCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, revit_repository, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model
        self.__revit_repository = revit_repository
        self.__view_model.PropertyChanged += self.ViewModel_PropertyChanged

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def ViewModel_PropertyChanged(self, sender, e):
        self.OnCanExecuteChanged()

    def CanExecute(self, parameter):
        if not self.__view_model.curve_element:
            self.__view_model.error_text = "Выберите линию."
            return False

        if not isinstance(self.__view_model.curve_element, CurveElement):
            self.__view_model.error_text = "Выбранный элемент должен быть линией."
            return False

        if not self.__view_model.param_name:
            self.__view_model.error_text = "Параметр должен быть заполнен."
            return False

        if not is_int(self.__view_model.start_number):
            self.__view_model.error_text = "Начальный номер должен быть числом."
            return False

        if int(self.__view_model.start_number) <= 0:
            self.__view_model.error_text = "Начальный номер должен быть положительным числом."
            return False

        self.__view_model.error_text = None
        return True

    def Execute(self, parameter):
        output = script.get_output()
        stopwatch = Stopwatch.StartNew()

        view_model = self.__view_model
        selected_rooms = self.__revit_repository.get_filtered_rooms_by_group()
        selected_room_ids = [x.room_obj.Id for x in selected_rooms]
        selected_curve = view_model.curve_element.Location.Curve
        room_number = int(view_model.start_number)
        rooms_set = set()
        fix_param = ProjectParamsConfig.Instance.IsRoomNumberFix
        phase_id = document.ActiveView.GetParamValueOrDefault(BuiltInParameter.VIEW_PHASE)
        phase = document.GetElement(phase_id)

        try:
            with revit.Transaction("BIM: Нумерация по линии"):
                index_points = get_index_points(selected_curve)
                rooms = [document.GetRoomAtPoint(x, phase) for x in index_points]
                rooms = [x for x in rooms if x and x.Id in selected_room_ids]

                for room in rooms:
                    if room.Id not in rooms_set:
                        if not room.GetParamValueOrDefault(fix_param):
                            value = view_model.prefix + str(room_number) + view_model.suffix
                            room.SetParamValue(view_model.param_name, value)

                            log_information(
                                "Id: {} Room Number: {}".format(output.linkify(room.Id), room_number))

                            rooms_set.add(room.Id)
                            room_number += 1

                alert("Последний назначенный номер: {}".format(room_number - 1))

        finally:
            stopwatch.Stop()
            log_elapsed_time("Operations Elapsed: {}".format(stopwatch.Elapsed))


class SelectLineCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view, view_model, revit_repository, *args):
        ICommand.__init__(self, *args)
        self.__view = view
        self.__view_model = view_model
        self.__revit_repository = revit_repository

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, System.EventArgs.Empty)

    def CanExecute(self, parameter):
        return True

    def Execute(self, parameter):
        self.__view.Hide()
        try:
            self.__view_model.curve_element = self.__revit_repository.pick_element("Выберите линию.")
        finally:
            self.__view.show_dialog()


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    revit_repository = RevitRepository(document, __revit__)
    if revit_repository.is_empty:
        alert("Выберите помещения для нумерации", exitscript=True)

    select_groups_window = SelectRoomGroupsWindow(revit_repository.room_groups)
    select_groups_window.show_dialog()
    if not revit_repository.get_filtered_rooms_by_group() or not select_groups_window.DialogResult:
        script.exit()

    main_window = MainWindow()
    main_window.DataContext = MainWindowViewModel(revit_repository, main_window)
    if not main_window.show_dialog():
        script.exit()


script_execute()
