# coding=utf-8

import clr

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import pyevent

from System.Windows.Input import ICommand
from System import EventArgs

from Autodesk.Revit.UI.Selection import ISelectionFilter
from Autodesk.Revit.DB.Architecture import RoomFilter, Room
from Autodesk.Revit.UI.Selection import ObjectType

import dosymep

clr.ImportExtensions(dosymep.Revit)
clr.ImportExtensions(dosymep.Bim4Everyone)

from pyrevit import forms
from pyrevit.forms import *
from pyrevit import revit
from pyrevit import script
from pyrevit import EXEC_PARAMS
from pyrevit.revit import HOST_APP

from dosymep_libs.bim4everyone import *

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument
active_view = doc.ActiveView


def elements_to_list(elements):
    return [el for el in elements]


def convert_value(value):
    if HOST_APP.is_older_than(2022):
        return UnitUtils.ConvertToInternalUnits(int(value), DisplayUnitType.DUT_MILLIMETERS)
    else:
        return UnitUtils.ConvertToInternalUnits(int(value), UnitTypeId.Millimeters)


def is_int(value):
    try:
        int(value)
        return True
    except:
        return False


class ClassISelectionFilter(ISelectionFilter):
    def __init__(self, element_class):
        self.element_class = element_class

    def AllowElement(self, elem):
        return isinstance(elem, self.element_class) and elem.Area > 0

    def AllowReference(self, ref, point):
        return True


class RevitRepository:
    def __init__(self, doc):
        self.doc = doc
        self.__floor_types = self.__collect_floor_types()
        self.__all_rooms = self.__collect_all_rooms()
        self.__rooms_on_active_view = self.__collect_rooms_on_active_view()
        self.__room_parameters = self.__get_room_parameters()
        self.__selected_rooms = self.__get_selected_rooms()

    @reactive
    def floor_types(self):
        return self.__floor_types

    def __collect_floor_types(self):
        all_floor_types = FilteredElementCollector(doc) \
            .WhereElementIsElementType() \
            .OfCategory(BuiltInCategory.OST_Floors)
        return elements_to_list(all_floor_types)

    @reactive
    def rooms_on_active_view(self):
        return self.__rooms_on_active_view

    def __collect_rooms_on_active_view(self):
        '''
        Функция возвращает размещенные помещения на активном виде, у которых значение параметра "Площадь" больше 0
        '''
        room_filter = RoomFilter()
        all_rooms = FilteredElementCollector(doc, active_view.Id) \
            .WherePasses(room_filter) \
            .ToElements()
        correct_rooms = [room for room in all_rooms if room.Area > 0]
        return correct_rooms

    @reactive
    def all_rooms(self):
        return self.__all_rooms

    def __collect_all_rooms(self):
        '''
        Функция возвращает размещенные помещения, у которых значение параметра "Площадь" больше 0
        '''
        room_filter = RoomFilter()
        all_rooms = FilteredElementCollector(doc) \
            .WherePasses(room_filter) \
            .ToElements()
        correct_rooms = [room for room in all_rooms if
                         room.Location is not None and room.Area > 0]
        return correct_rooms

    @staticmethod
    def select_rooms_on_view(title):
        '''
        Функция реализует выбор элементов при помощи интерфейса ISelectionFilter и возвращает список выбранных
        пользователем помещений
        '''
        with WarningBar(title=title):
            ref_list = uidoc.Selection.PickObjects(ObjectType.Element, ClassISelectionFilter(Room))
            elements = [doc.GetElement(el) for el in ref_list]
            return elements

    @reactive
    def room_parameters(self):
        return self.__room_parameters

    def __get_room_parameters(self):
        room_filter = RoomFilter()
        room = FilteredElementCollector(doc) \
            .WherePasses(room_filter) \
            .FirstElement()
        if room is not None:
            parameters_list = [p.Definition.Name for p in room.Parameters]
            return parameters_list
        return

    @reactive
    def selected_rooms(self):
        return self.__selected_rooms

    def __get_selected_rooms(self):
        selected_element_ids = uidoc.Selection.GetElementIds()
        elements = [doc.GetElement(el) for el in selected_element_ids if
                    isinstance(doc.GetElement(el), Room) and doc.GetElement(el).Area > 0]
        return elements


class RoomContour:
    def __init__(self, room):
        self.room = room

    def get_curve_loops_of_room(self):
        '''
        Возвращает список замкнутых петель (с упрощенными кривыми) из границ помещения (для Revit 2022 и новее)
        '''
        spatial_element_boundary_options = SpatialElementBoundaryOptions()
        curve_loops = []
        loops = self.room.GetBoundarySegments(spatial_element_boundary_options)
        if HOST_APP.is_newer_than(2021):
            for loop in loops:
                curves = []
                for i in range(len(loop)):
                    curves.append(loop[i].GetCurve())
                curve_loops.append(self.simplify(curves))
            return curve_loops

    def get_curve_arrays_of_room(self):
        '''
        Возвращает самый длинный массив кривых (ограничивающий контур) из границ помещения, а также список массивов
        кривых, если они есть внутри помещения (для Revit 2021 и старше)
        '''
        spatial_element_boundary_options = SpatialElementBoundaryOptions()
        loops = self.room.GetBoundarySegments(spatial_element_boundary_options)
        if HOST_APP.is_older_than(2022):
            res_curve_array = None
            prev_max_length = 0
            curves_for_openings = []
            for loop in loops:
                curve = []
                current_length = 0
                for i in range(len(loop)):
                    curve.append(loop[i].GetCurve())
                for c in curve:
                    current_length += c.Length
                if current_length > prev_max_length:
                    prev_max_length = current_length
                    res_curve_array = curve
                else:
                    curves_for_openings.append(self.simplify(curve))

            correct_curve_array = self.simplify(res_curve_array)
            return correct_curve_array, curves_for_openings

    def are_join(self, curve, next_curve):
        '''
        Проверяет, соединен ли конец (XY) 1-й кривой и начало (XY) 2-й кривой
        curve: текущая кривая
        next_curve: следующая кривая
        return: True, если 2 кривые имеют общую точку соединения, иначе False
        '''

        x1, x2 = curve.GetEndPoint(1)[0], next_curve.GetEndPoint(0)[0]
        diff_x = abs(x1 - x2)

        y1, y2 = curve.GetEndPoint(1)[1], next_curve.GetEndPoint(0)[1]
        diff_y = abs(y1 - y2)

        res = diff_x < 0.01 and diff_y < 0.01

        return res

    def append_curve(self, curve, next_curve):
        '''
        Создает одну прямую линию из двух, если они являются прямыми и коллинеарными и если конечная точка первой
        совпадает с начальной точкой второй
        curve: текущая кривая
        next_curve: следующая кривая
        return: True и новую кривую, если слияние кривых возможно и прошло успешно, иначе False и ту же самую кривую
        '''
        if curve is not None and next_curve is not None:
            curve_vector = (curve.GetEndPoint(1) - curve.GetEndPoint(0)).Normalize()
            add_curve_vector = (next_curve.GetEndPoint(1) - next_curve.GetEndPoint(0)).Normalize()
            are_collinear = (isinstance(curve, Line) and isinstance(next_curve, Line)) and curve_vector.IsAlmostEqualTo(
                add_curve_vector)
            are_join = self.are_join(curve, next_curve)
            if are_collinear and are_join:
                new_curve = Line.CreateBound(curve.GetEndPoint(0), next_curve.GetEndPoint(1))
                return True, new_curve
        return False, curve

    def simplify(self, curves_list):
        '''
        Соединяет кривые у замкнутой петли (Loop), лежащие на одной прямой и возвращает новую упрощенную
        замкнутую петлю (Loop)
        curves_list: Список кривых
        return: Новая петля с оптимизированными кривыми, которые лежали на одной прямой друг за другом
        '''
        correct_curves = []
        curve_prev = None
        for i in range(len(curves_list)):
            curve_current = curves_list[i]
            (curve_added, curve_prev) = self.append_curve(curve_prev, curve_current)
            if curve_prev is None:
                curve_prev = curve_current
                continue
            if i != 0 and i != (len(curves_list) - 1) and (not curve_added):
                correct_curves.append(curve_prev)
                curve_prev = curve_current
                continue
            if i == (len(curves_list) - 1):
                if curve_added:
                    correct_curves.append(curve_prev)
                else:
                    correct_curves.append(curve_prev)
                    correct_curves.append(curve_current)
        if HOST_APP.is_newer_than(2021):
            simplified_curve_loop = CurveLoop()
            for curve in correct_curves:
                simplified_curve_loop.Append(curve)
            return simplified_curve_loop
        else:
            simplified_curve_array = CurveArray()
            for curve in correct_curves:
                simplified_curve_array.Append(curve)
            return simplified_curve_array

    def create_virtual_solid_of_room(self):
        curve_loops = self.get_curve_loops_of_room()
        max_length = 0
        boundary_curve = curve_loops[0]
        for curve_loop in curve_loops:
            current_length = curve_loop.GetExactLength()
            if current_length > max_length:
                max_length = current_length
                boundary_curve = curve_loop

        new_curve_loop = boundary_curve.CreateViaOffset(boundary_curve, 0.2, XYZ(0, 0, 1))
        virtual_solid = GeometryCreationUtilities.CreateExtrusionGeometry([new_curve_loop], XYZ(0, 0, 1), 10)

        return virtual_solid

    def get_doors_from_room(self):
        '''
        Возвращает список всех дверей, которые пересекают помещение
        '''
        virtual_solid = self.create_virtual_solid_of_room()

        intersect_filter = ElementIntersectsSolidFilter(virtual_solid)
        doors = (FilteredElementCollector(doc, active_view.Id)
                 .WhereElementIsNotElementType()
                 .OfCategory(BuiltInCategory.OST_Doors)
                 .WherePasses(intersect_filter))
        list_doors = elements_to_list(doors)

        return list_doors


class CreateFloorsByRooms:

    def floor_create(self, room, floor_type, level_offset=0):
        '''
        Создает перекрытие на основе CurveLoop помещения и его уровня, заданным типоразмером перекрытия со смещением
        от уровня (опционально)
        room: помещение, на основе которого будет создано перекрытие
        floor_type: типоразмер перекрытия, который будет указан для создания
        level_offset: смещение от уровня (по умолчанию 0)
        '''
        if HOST_APP.is_older_than(2022):
            curve_array = RoomContour(room).get_curve_arrays_of_room()[0]
            level = doc.GetElement(room.LevelId)
            current_floor = doc.Create.NewFloor(curve_array, floor_type, level, False)

        else:
            curve_loops = RoomContour(room).get_curve_loops_of_room()
            level_id = room.LevelId
            current_floor = Floor.Create(doc, curve_loops, floor_type.Id, level_id)

        converted_level_offset = convert_value(level_offset)
        current_floor.SetParamValue(BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM, converted_level_offset)

        return current_floor

    def openings_create(self, floor, curves):
        '''
        Создает элемент категории "Вырезание проема в перекрытии" для указанного перекрытия
        '''
        if len(curves) != 0:
            for curve in curves:
                doc.Create.NewOpening(floor, curve, True)

    def create_floors_by_rooms_on_view(self, rooms, floor_type, level_offset=0):
        '''
        Создает перекрытия последовательно по помещениям в выборке, используя функцию создания перекрытия по помещению
        Для Revit версии 2021 и старше создаются вырезания в перекрытии отдельной транзакцией, если контур помещения
        состоит из нескольких окружающих кривых
        floor_type: типоразмер перекрытия, который будет указан для создания
        level_offset: смещение от уровня (по умолчанию 0)
        '''
        if HOST_APP.is_older_than(2022):
            with revit.Transaction("BIM: Создание перекрытий"):
                rooms_and_floors_dict = {}
                for room in rooms:
                    floor = self.floor_create(room, floor_type, level_offset)
                    rooms_and_floors_dict[room] = floor

            with revit.Transaction("BIM: Создание отверстий в перекрытии"):
                for r, fl in rooms_and_floors_dict.items():
                    opening_curve_arrays = RoomContour(r).get_curve_arrays_of_room()[1]
                    self.openings_create(fl, opening_curve_arrays)
        else:
            with revit.Transaction("BIM: Создание перекрытий"):
                for room in rooms:
                    self.floor_create(room, floor_type, level_offset)


class CreateFloorsByRoomsCommand(ICommand):
    CanExecuteChanged, _canExecuteChanged = pyevent.make_event()

    def __init__(self, view_model, *args):
        ICommand.__init__(self, *args)
        self.__view_model = view_model
        self.__view_model.PropertyChanged += self.ViewModel_PropertyChanged
        self.__create_floors_by_view = CreateFloorsByRooms()
        self.__revit_repository = RevitRepository(doc)

    def add_CanExecuteChanged(self, value):
        self.CanExecuteChanged += value

    def remove_CanExecuteChanged(self, value):
        self.CanExecuteChanged -= value

    def OnCanExecuteChanged(self):
        self._canExecuteChanged(self, EventArgs.Empty)

    def ViewModel_PropertyChanged(self, sender, e):
        self.OnCanExecuteChanged()

    def CanExecute(self, parameter):
        if not is_int(self.__view_model.level_offset):
            self.__view_model.error_text = "Введите целое число"
            return False

        self.__view_model.error_text = None
        return True

    def Execute(self, parameter):
        if self.__view_model.is_checked_selected:
            # Если пользователь выбрал создать перекрытия по предварительно выбранным помещениям
            self.__create_floors_by_view.create_floors_by_rooms_on_view(self.__view_model.selected_rooms,
                                                                        self.__view_model.selected_floor_type,
                                                                        self.__view_model.level_offset)

        elif self.__view_model.is_checked_select:
            # Если пользователь выбрал создать перекрытия по выбранным помещениям

            select_rooms = self.__revit_repository.select_rooms_on_view("Выберите помещения")
            self.__create_floors_by_view.create_floors_by_rooms_on_view(select_rooms,
                                                                        self.__view_model.selected_floor_type,
                                                                        self.__view_model.level_offset)

        elif self.__view_model.is_checked_on_view:
            # Если пользователь выбрал создать перекрытия на активном виде

            self.__create_floors_by_view.create_floors_by_rooms_on_view(self.__view_model.rooms_on_active_view,
                                                                        self.__view_model.selected_floor_type,
                                                                        self.__view_model.level_offset)


class MainWindow(WPFWindow):
    def __init__(self):
        self._context = None
        self.xaml_source = op.join(op.dirname(__file__), "MainWindow.xaml")
        super(MainWindow, self).__init__(self.xaml_source)

    def ButtonOk_Click(self, sender, e):
        self.DialogResult = True


class MainWindowViewModel(Reactive):
    def __init__(self, revit_repository):
        Reactive.__init__(self)
        self.__revit_repository = revit_repository
        self.__floor_types = revit_repository.floor_types
        self.__rooms_on_active_view = revit_repository.rooms_on_active_view

        if len(self.__floor_types) > 0:
            self.__selected_floor_type = self.floor_types[0]

        self.__level_offset = "0"
        self.__selected_rooms = revit_repository.selected_rooms
        self.__is_checked_select = True
        self.__is_checked_on_view = False
        self.__is_checked_selected = False
        if len(self.__selected_rooms):
            self.__is_checked_on_view_visibility = "Visible"
            self.__is_checked_selected_content = ("По предварительно выбранным помещениям ({})"
                                                  .format(len(self.__selected_rooms)))
            self.__is_checked_selected = True
            self.__is_checked_select = False
        else:
            self.__is_checked_on_view_visibility = "Hidden"

        self.__room_parameters = revit_repository.room_parameters
        self.__error_text = ""
        self.__create_floors_by_rooms = CreateFloorsByRoomsCommand(self)

    @reactive
    def floor_types(self):
        return self.__floor_types

    @reactive
    def rooms_on_active_view(self):
        return self.__rooms_on_active_view

    @reactive
    def selected_floor_type(self):
        return self.__selected_floor_type

    @property
    def create_floors_by_rooms(self):
        return self.__create_floors_by_rooms

    @reactive
    def selected_floor_type(self):
        return self.__selected_floor_type

    @selected_floor_type.setter
    def selected_floor_type(self, value):
        self.__selected_floor_type = value

    @reactive
    def level_offset(self):
        return self.__level_offset

    @level_offset.setter
    def level_offset(self, value):
        self.__level_offset = value

    @reactive
    def is_checked_selected(self):
        return self.__is_checked_selected

    @is_checked_selected.setter
    def is_checked_selected(self, value):
        self.__is_checked_selected = value

    @reactive
    def is_checked_selected_content(self):
        return self.__is_checked_selected_content

    @reactive
    def is_checked_select(self):
        return self.__is_checked_select

    @is_checked_select.setter
    def is_checked_select(self, value):
        self.__is_checked_select = value

    @reactive
    def is_checked_on_view(self):
        return self.__is_checked_on_view

    @is_checked_on_view.setter
    def is_checked_on_view(self, value):
        self.__is_checked_on_view = value

    @reactive
    def is_checked_on_view_visibility(self):
        return self.__is_checked_on_view_visibility

    @reactive
    def room_parameters(self):
        return self.__room_parameters

    @reactive
    def selected_rooms(self):
        return self.__selected_rooms

    @reactive
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value


@notification()
@log_plugin(EXEC_PARAMS.command_name)
def script_execute(plugin_logger):
    revit_info = RevitRepository(doc)

    all_rooms = revit_info.all_rooms

    # Проверка на неразмещенные помещения с площадью == 0
    if len(all_rooms) == 0:
        forms.alert("В проекте отсутствуют размещенные помещения", exitscript=True)

    rooms_on_active_view = revit_info.rooms_on_active_view

    # Проверка наличия окруженных помещений на активном виде
    if len(rooms_on_active_view) == 0:
        forms.alert("На текущем виде нет окруженных помещений!", exitscript=True)

    main_window = MainWindow()
    main_window.DataContext = MainWindowViewModel(revit_info)
    main_window.show_dialog()
    if not main_window.DialogResult:
        script.exit()


script_execute()
