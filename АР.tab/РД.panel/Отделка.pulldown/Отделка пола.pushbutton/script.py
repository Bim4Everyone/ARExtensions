# coding=utf-8

import clr

# from clr import StrongBox

clr.AddReference("dosymep.Revit.dll")
clr.AddReference("dosymep.Bim4Everyone.dll")

import pyevent

from System.Windows.Input import ICommand
from System import EventArgs

from Autodesk.Revit.UI.Selection import ISelectionFilter
from Autodesk.Revit.DB.Architecture import RoomFilter, Room
from Autodesk.Revit.UI.Selection import ObjectType

import dosymep
from dosymep_libs.bim4everyone import *

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


def convert_from_millimeters_to_feet(value):
    if HOST_APP.is_older_than(2022):
        return UnitUtils.ConvertToInternalUnits(int(value), DisplayUnitType.DUT_MILLIMETERS)
    else:
        return UnitUtils.ConvertToInternalUnits(int(value), UnitTypeId.Millimeters)


def convert_to_millimeters_from_feet(value):
    if HOST_APP.is_older_than(2022):
        return UnitUtils.ConvertFromInternalUnits(value, DisplayUnitType.DUT_MILLIMETERS)
    else:
        return UnitUtils.ConvertFromInternalUnits(value, UnitTypeId.Millimeters)


def is_int(value):
    try:
        int(value)
        return True
    except:
        return False


def show_error_message(room_ids):
    output = script.get_output()
    output.insert_divider(level="Не удалось создать пол по контуру помещения:")
    for idx, elid in enumerate(room_ids):
        print('{}:{}'.format(idx + 1, output.linkify(elid)))


class ClassISelectionFilter(ISelectionFilter):
    def __init__(self, element_class):
        self.element_class = element_class

    def AllowElement(self, elem):
        return isinstance(elem, self.element_class) and elem.Area > 0

    def AllowReference(self, ref, point):
        return True


class RevitRepository:
    def __init__(self, doc):
        self.__doc = doc

    @property
    def floor_types(self):
        all_floor_types = FilteredElementCollector(self.__doc) \
            .WhereElementIsElementType() \
            .OfCategory(BuiltInCategory.OST_Floors)
        return list(all_floor_types)

    @property
    def rooms_on_active_view(self):
        '''
        Функция возвращает размещенные помещения на активном виде, у которых значение параметра "Площадь" больше 0
        '''
        room_filter = RoomFilter()
        all_rooms = FilteredElementCollector(self.__doc, active_view.Id) \
            .WherePasses(room_filter) \
            .ToElements()
        correct_rooms = [room for room in all_rooms if room.Area > 0]
        return correct_rooms

    @property
    def all_rooms(self):
        '''
        Функция возвращает размещенные помещения, у которых значение параметра "Площадь" больше 0
        '''
        room_filter = RoomFilter()
        all_rooms = FilteredElementCollector(self.__doc) \
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

    @property
    def selected_rooms(self):
        '''
        Функция возвращает список помещений, выбранных пользователем до запуска скрипта
        '''
        selected_element_ids = uidoc.Selection.GetElementIds()
        elements = [self.__doc.GetElement(el) for el in selected_element_ids if
                    isinstance(self.__doc.GetElement(el), Room) and self.__doc.GetElement(el).Area > 0]
        return elements

    @property
    def all_doors_on_active_view(self):
        doors = FilteredElementCollector(self.__doc, active_view.Id).WhereElementIsNotElementType().OfCategory(
            BuiltInCategory.OST_Doors).ToElements()
        elements = list(doors)
        return elements

    @property
    def phase(self):
        phase = self.__doc.GetElement(active_view.get_Parameter(BuiltInParameter.VIEW_PHASE).AsElementId())
        return phase


class PluginConfig:
    def __init__(self, floor_type='', door_contour_option='', door_opening_option='', door_contour_offset='',
                 level_offset='', offset_into_room=''):
        self.__floor_type = floor_type
        self.__door_contour_option = door_contour_option
        self.__door_opening_option = door_opening_option
        self.__door_contour_offset = door_contour_offset
        self.__level_offset = level_offset
        self.__offset_into_room = offset_into_room

    def floor_type(self):
        return self.__floor_type

    def door_contour_option(self):
        return self.__door_contour_option

    def door_opening_option(self):
        return self.__door_opening_option

    def door_contour_offset(self):
        return self.__door_contour_offset

    def level_offset(self):
        return self.__level_offset

    def offset_into_room(self):
        return self.__offset_into_room


class DoorContourOption:

    def create_contour(self, room, door, plugin_options):
        raise NotImplementedError("Подкласс должен реализовать абстрактный метод")

    @property
    def name(self):
        raise NotImplementedError("Подкласс должен реализовать абстрактное свойство")


class ContourNotCreate(DoorContourOption):
    def create_contour(self, room, door, plugin_options):
        return None

    @property
    def name(self):
        return "Не заводить контур пола в дверные проемы"


class ContourCreateFullThickness(DoorContourOption):
    def create_contour(self, room, door, plugin_options):
        door_contour = DoorContourFactory(room, door, plugin_options)
        info_for_create = door_contour.get_info_for_full_thickness(plugin_options)
        return door_contour.create_rectangle_door_curve_loop(info_for_create)

    @property
    def name(self):
        return "Заводить контур на всю толщину стены"


class ContourCreateToTheMiddle(DoorContourOption):
    def create_contour(self, room, door, plugin_options):
        door_contour = DoorContourFactory(room, door, plugin_options)
        info_for_create = door_contour.get_info_for_middle(plugin_options)
        return door_contour.create_rectangle_door_curve_loop(info_for_create)

    @property
    def name(self):
        return "Заводить контур до середины стены"


class ContourCreateForSpecifiedLength(DoorContourOption):

    def create_contour(self, room, door, plugin_options):
        door_contour = DoorContourFactory(room, door, plugin_options)
        if not door_contour.check_door_z_location(plugin_options):
            return None
        info_for_create = door_contour.get_info_for_specified_line(plugin_options)
        return door_contour.create_rectangle_door_curve_loop(info_for_create)

    @property
    def name(self):
        return "Заводить контур на указанное значение, мм"


class DoorOpeningOption:

    def can_create(self, room, door, revit_info):
        raise NotImplementedError("Подкласс должен реализовать абстрактный метод")

    @property
    def name(self):
        raise NotImplementedError("Подкласс должен реализовать абстрактное свойство")


class DoorOpeningInAnyDirection(DoorOpeningOption):

    def can_create(self, room, door, revit_info):
        return True

    @property
    def name(self):
        return "Открывание в любую сторону"


class DoorOpeningOutside(DoorOpeningOption):

    def can_create(self, room, door, revit_info):
        res = False
        phase = revit_info.phase
        room_id = room.Id
        if door.FromRoom[phase].Id == room_id:
            res = True
        return res

    @property
    def name(self):
        return "Открывание наружу"


class DoorOpeningInside(DoorOpeningOption):

    def can_create(self, room, door, revit_info):
        res = False
        phase = revit_info.phase
        room_id = room.Id
        if door.ToRoom[phase].Id == room_id:
            res = True
        return res

    @property
    def name(self):
        return "Открывание внутрь"


class DirectionEnum:
    def __init__(self):
        pass

    @property
    def left(self):
        return "left"

    @property
    def right(self):
        return "right"

    @property
    def top(self):
        return "top"

    @property
    def bottom(self):
        return "bottom"


class LineMerging:
    def __init__(self):
        pass

    def create_one_line_from_two_segments(self, prev_line, current_line):
        '''
        Создает новую линию из начальной точки предыдущей линии и конечной текущей линии
        prev_line: предыдущая линия
        current_line: текущая линия
        return: новая линия, из начальных координат предыдущей и конечных координат текущей
        '''
        start_point = prev_line.GetEndPoint(0)
        end_point = current_line.GetEndPoint(1)
        new_line = Line.CreateBound(start_point, end_point)
        return new_line

    def create_new_line_from_segments(self, segments):
        '''
        Создает одну линию из отрезков линий, полученных из сегментов SolidCurveIntersection
        segments: сегменты линий, полученные из SolidCurveIntersection
        return: новая линия, созданная из полученных сегментов
        '''
        for i in range(segments.SegmentCount):
            current_line = segments.GetCurveSegment(i)
            if i == 0:
                prev_line = segments.GetCurveSegment(i)
                continue
            new_line = self.create_one_line_from_two_segments(prev_line, current_line)
            prev_line = current_line
        return new_line


class DoorWithPoints:
    def __init__(self, door):
        self.__door = door
        self.__points = self.__create_two_points()

    @property
    def revit_door(self):
        return self.__door

    @property
    def points(self):
        return self.__points

    def __create_two_points(self):
        '''
        Создает на определенном расстоянии 2 точки от центра двери в направлении перпендикулярном ширине двери со
        смещением 200мм по высоте от низа вставки двери
        return: точка, находящаяся сверху от двери в плане; точка, находящаяся снизу от двери в плане
        '''
        z_offset = convert_from_millimeters_to_feet(1000)  # смещение по высоте от низа дверного проема, мм
        top_bottom_offset = convert_from_millimeters_to_feet(
            600)  # смещение в плане вперед/назад от центра точки вставки двери,мм
        door_location = DoorContourFactory.get_door_location(self.__door)
        if door_location is None:
            return None
        door_vector = DoorContourFactory.get_vector_from_door(self.__door)
        z = z_offset + door_location.Z
        dist_const_top_bottom = top_bottom_offset
        top_point = XYZ(door_location.X, door_location.Y, z) + door_vector * dist_const_top_bottom
        bottom_point = XYZ(door_location.X, door_location.Y, z) - door_vector * dist_const_top_bottom

        return top_point, bottom_point


class SolidOperations:
    def __init__(self):
        pass

    def get_solid_from_element(self, element):
        '''
        Возвращает Solid из элемента
        element: указанный элемент Revit
        return: Solid элемента
        '''
        opt = Options()
        opt.DetailLevel = ViewDetailLevel.Fine
        geo = element.get_Geometry(opt)
        for s in geo:
            if isinstance(s, Solid):
                result_solid = s
                break
        return result_solid

    def get_solid_from_host_walls(self, door):
        '''
        Возвращает объединенный Solid из стен, которые присоединены к основе стены двери.
        door: дверь, из которой будет взята основа-стена.
        return: объединенный Solid из стен, которые присоединены к основе-стене двери
        '''
        opt = Options()
        opt.DetailLevel = ViewDetailLevel.Fine
        wall = door.Host
        host_solid = self.get_solid_from_element(wall)
        joined_element_ids = JoinGeometryUtils.GetJoinedElements(doc, wall)
        joined_elements = [doc.GetElement(wall) for wall in joined_element_ids]
        if len(joined_elements) > 0:
            for i in range(len(joined_elements)):
                current_solid = self.get_solid_from_element(joined_elements[i])
                if i == 0:
                    prev_solid = host_solid
                    res_solid = BooleanOperationsUtils.ExecuteBooleanOperation(prev_solid, current_solid,
                                                                               BooleanOperationsType.Union)
                else:
                    res_solid = BooleanOperationsUtils.ExecuteBooleanOperation(prev_solid, current_solid,
                                                                               BooleanOperationsType.Union)
                prev_solid = res_solid

            return res_solid
        return host_solid


class DoorContourParams:
    def __init__(self):
        self.__start_point = None
        self.__line_of_door_thickness = None
        self.__distance = None
        self.__is_right = None
        self.__door_width = None
        self.__door_vector = None
        self.__boundary_point_of_center_room = None

    @property
    def start_point(self):
        return self.__start_point

    @start_point.setter
    def start_point(self, value):
        self.__start_point = value

    @property
    def line_of_door_thickness(self):
        return self.__line_of_door_thickness

    @line_of_door_thickness.setter
    def line_of_door_thickness(self, value):
        self.__line_of_door_thickness = value

    @property
    def distance(self):
        return self.__distance

    @distance.setter
    def distance(self, value):
        self.__distance = value

    @property
    def is_right(self):
        return self.__is_right

    @is_right.setter
    def is_right(self, value):
        self.__is_right = value

    @property
    def door_width(self):
        return self.__door_width

    @door_width.setter
    def door_width(self, value):
        self.__door_width = value

    @property
    def door_vector(self):
        return self.__door_vector

    @door_vector.setter
    def door_vector(self, value):
        self.__door_vector = value

    @property
    def boundary_point_of_center_room(self):
        return self.__boundary_point_of_center_room

    @boundary_point_of_center_room.setter
    def boundary_point_of_center_room(self, value):
        self.__boundary_point_of_center_room = value


def create_direct_shape(solid):
    directShape = DirectShape.CreateElement(doc, ElementId(BuiltInCategory.OST_GenericModel))

    # Устанавливаем геометрию для DirectShape
    directShape.SetShape([solid])
    return directShape


class DoorContourFactory:
    def __init__(self, room, door, plugin_options):
        self.solid_operations = SolidOperations()
        self.room = room
        self.revit_info = RevitRepository(doc)
        self.simplify_line = LineMerging()
        self.room_contour = RoomWallsContour(self.room, plugin_options)
        self.door = door
        self.plugin_options = plugin_options

    def get_boundary_point_from_room_in_door_center(self, room_solid):
        '''
        Находит точку, находящуюся на грани ограничивающего контура помещения в плоскости центра дверного проема
        room_solid: Solid помещения, у которого будет выполнен поиск точки на ограничивающем контуре, ближайшем к центру
        дверного проема
        return: точка, полученная при пересечении линии, запущенной из центра дверного проема и Solid помещения
        '''
        line, is_right = self.create_line_from_door(DirectionEnum.top)
        intersect_opt_inside = SolidCurveIntersectionOptions()
        intersect_opt_outside = SolidCurveIntersectionOptions()
        intersect_opt_outside.ResultType = SolidCurveIntersectionMode.CurveSegmentsOutside
        intersect = room_solid.IntersectWithCurve(line, intersect_opt_inside)
        if intersect.SegmentCount < 1:
            # Если линия, запущенная вверх не пересекла Solid помещения - создание линии по направлению вниз от проема
            # и повторная проверка на пересечение
            line, is_right = self.create_line_from_door(DirectionEnum.bottom)
            intersect = room_solid.IntersectWithCurve(line, intersect_opt_inside)
            if intersect.SegmentCount > 0:
                # Если линия, запущенная вверх пересекла Solid помещения - замена результата проверки на внешние кривые
                intersect = room_solid.IntersectWithCurve(line, intersect_opt_outside)
        else:
            # Если линия, запущенная вверх пересекла Solid помещения - замена результата проверки на внешние кривые
            intersect = room_solid.IntersectWithCurve(line, intersect_opt_outside)
        line_to_room = intersect.GetCurveSegment(0)
        intersect_coord = line_to_room.GetEndPoint(1)
        return intersect_coord

    def create_line_from_door(self, direction="right"):
        '''
        Создает линию из центра дверного проема, поднятую на определенное расстояние, в сторону стен (вправо или влево
        от проема) с длиной равной константе, в мм
        mode: режим создания линии - вправо, влево, вверх или вниз от центра дверного проема в плане ("right", "left",
        "top", "bottom")
        return: line - линия, созданная из центра дверного проема; is_right - направление линии - True, если линия
        вправо, False - влево, используется также и для режимов "top" и "bottom"
        '''
        z_offset_const = convert_from_millimeters_to_feet(1000)  # отступ от низа дверного проема, мм
        door_location = self.get_door_location(self.door)
        if door_location is None:
            return None
        door_vector = self.get_vector_from_door(self.door)
        normal_vector = XYZ.BasisZ.CrossProduct(door_vector).Normalize()
        dist_const_z = z_offset_const + door_location.Z
        dist_const_left_right = convert_from_millimeters_to_feet(6000)  # длина линии, запущенной влево/вправо
        dist_const_top_bottom = convert_from_millimeters_to_feet(500)  # длина линии, запущенной вперед/назад
        start_point = XYZ(door_location.X, door_location.Y, dist_const_z)
        is_right = True
        end_point = XYZ(door_location.X, door_location.Y, dist_const_z) + normal_vector * dist_const_left_right
        if direction == DirectionEnum.left:
            end_point = XYZ(door_location.X, door_location.Y, dist_const_z) - normal_vector * dist_const_left_right
            is_right = False
        if direction == DirectionEnum.top:
            end_point = XYZ(door_location.X, door_location.Y, dist_const_z) + door_vector * dist_const_top_bottom
        if direction == DirectionEnum.bottom:
            end_point = XYZ(door_location.X, door_location.Y, dist_const_z) - door_vector * dist_const_top_bottom
            is_right = False
        line = Line.CreateBound(start_point, end_point)
        return line, is_right

    def create_line_from_xyz(self, point, is_right=True):
        '''
        Создает линию, перпендикулярную ширине проема, из указанной точки, равной константе, в мм
        point: точка, которая будет являться центром создаваемой линии
        is_right: bool направления создания до этого линии из центра проема (True - вправо, False - влево)
        return: линия, созданная перпендикулярно ширине проема
        '''
        dist_const = convert_from_millimeters_to_feet(1000)  # длина линии запускаемой линии в мм
        door_vector = self.get_vector_from_door(self.door)
        start_point = point + door_vector * dist_const
        end_point = point - door_vector * dist_const
        if not is_right:
            start_point = point - door_vector * dist_const
            end_point = point + door_vector * dist_const
        line = Line.CreateBound(start_point, end_point)
        return line

    def create_rectangle_door_curve_loop(self, info_for_create):
        '''
        Создает петлю кривых контура дверного проема, начинающегося из короткой линии, обозначающую толщину проема
        is_right: bool направления создания до этого линии из центра проема (True - вправо, False - влево)
        door_normal: нормаль двери для нахождения вектора направления вдоль дверного проема
        rectangle_width: ширина дверного проема
        short_line: короткая линия, обозначающая толщину проема и построенная по грани стены внутри дверного проема
        return: петля кривых (CurveLoop()) дверного проема в форме прямоугольника
        '''

        alongside_vector = XYZ.BasisZ.CrossProduct(info_for_create.door_vector).Normalize()
        short_line = info_for_create.line_of_door_thickness
        start_point = short_line.GetEndPoint(1)

        res_curve_loop = CurveLoop()
        rectangle_width = -info_for_create.door_width
        if info_for_create.is_right:
            alongside_vector = -alongside_vector
        end_point = start_point + alongside_vector * abs(rectangle_width)
        long_line = Line.CreateBound(start_point, end_point)

        second_short_line = Line.CreateBound(long_line.GetEndPoint(1),
                                             short_line.GetEndPoint(0) + alongside_vector * abs(rectangle_width))

        second_long_line = Line.CreateBound(second_short_line.GetEndPoint(1), short_line.GetEndPoint(0))
        center_point_of_second_long_line = second_long_line.Evaluate(0.5, True)
        translation_vector = info_for_create.boundary_point_of_center_room - center_point_of_second_long_line
        second_long_line = second_long_line.CreateTransformed(Transform.CreateTranslation(translation_vector))
        start_moved_point = second_long_line.GetEndPoint(0)
        end_moved_point = second_long_line.GetEndPoint(1)

        short_line = Line.CreateBound(end_moved_point, short_line.GetEndPoint(1))
        second_short_line = Line.CreateBound(second_short_line.GetEndPoint(0), start_moved_point)
        # Последовательное создание петли кривых из линий
        res_curve_loop.Append(short_line)

        res_curve_loop.Append(long_line)

        res_curve_loop.Append(second_short_line)

        res_curve_loop.Append(second_long_line)

        return res_curve_loop

    def get_door_thickness_line(self, wall_solid, intersect_coord, is_right):
        '''
        Возвращает линию, равной толщине дверного проема для указанной двери, расположенную на грани стены
        wall_solid: Solid стен, присоединенных к стене-основе двери, включая саму основу-стену
        intersect_coord: точка пересечения линии, запущенной из центра дверного проема вправо/влево и Solid стен
        is_right: bool направления создания до этого линии из центра проема (True - вправо, False - влево)
        return: линия, расположенная на грани дверного проема (справа или слева), равная толщине этого проема
        '''
        # Создание линии, перпендикулярной линии, полученной из результата первого пересечения с линией вправо/влево
        line = self.create_line_from_xyz(intersect_coord, is_right)

        # Получение линии, соответствующей толщине дверного проема при помощи проверки на пересечение с Solid стен
        intersect_opt_inside = SolidCurveIntersectionOptions()
        second_intersect = wall_solid.IntersectWithCurve(line, intersect_opt_inside)
        line_of_door_thickness = second_intersect.GetCurveSegment(0)

        # Упрощение до 1 линии, если сегментов более 1
        if second_intersect.SegmentCount > 1:
            line_of_door_thickness = self.simplify_line.create_new_line_from_segments(second_intersect)

        return line_of_door_thickness

    def get_start_point_for_door_contour(self, line_of_door_thickness, boundary_point_in_door_center):
        '''
        Находит стартовую точку для построения контура дверного проема
        line_of_door_thickness: линия, лежащая на грани стены справа/слева от проема, с длиной, равной толщине проема
        boundary_point_in_door_center: точка, лежащая на грани ограничивающего контура помещения в плоскости центра
        дверного проема
        return: стартовая точка для построения контура проема
        '''
        points = []
        check_start_point = line_of_door_thickness.GetEndPoint(0)
        points.append(check_start_point)
        check_end_point = line_of_door_thickness.GetEndPoint(1)
        points.append(check_end_point)
        start_point = self.closest_point_to_target(boundary_point_in_door_center, points)
        return start_point

    def check_line_of_door_thickness(self, line_of_door_thickness, start_point):
        '''
        Возвращает отзеркаленную линию толщины проема, если это необходимо, в ином случае - возвращает ту же самую линию
        line_of_door_thickness: линия, лежащая на грани стены справа/слева от проема, с длиной, равной толщине проема
        start_point: стартовая точка для построения контура дверного проема
        return: линия толщины проема
        '''
        check_end_point = line_of_door_thickness.GetEndPoint(1)
        if start_point.X == check_end_point.X and start_point.Y == check_end_point.Y and start_point.Z == check_end_point.Z:
            line_of_door_thickness = line_of_door_thickness.CreateReversed()
        return line_of_door_thickness

    def get_info_for_full_thickness(self, plugin_options):
        '''
        Возвращает информацию для построения прямоугольного контура на всю толщину дверного проема
        plugin_options: настройки, которые выбрал пользователь в интерфейсе окна
        return: опции для построения прямоугольного контура дверного проема
        '''
        can_create_opening = plugin_options.door_opening_option.can_create(self.room, self.door, self.revit_info)
        can_create_z = self.check_door_z_location(plugin_options)
        if not can_create_opening or not can_create_z:
            return None
        options_for_create = self.get_base_info_for_door_contour()
        return options_for_create

    def get_info_for_middle(self, plugin_options):
        '''
        Возвращает информацию для построения прямоугольного контура на половину толщины дверного проема
        plugin_options: настройки, которые выбрал пользователь в интерфейсе окна
        return: опции для построения прямоугольного контура дверного проема
        '''
        options_for_create = self.get_base_info_for_door_contour()
        min_dist_for_evaluate = 2  # мм для деления линии наполовину
        can_create_z = self.check_door_z_location(plugin_options)
        if not can_create_z:
            return None

        if options_for_create.distance > min_dist_for_evaluate:
            end_point = options_for_create.line_of_door_thickness.Evaluate(0.5, True)
            if options_for_create.is_right:
                options_for_create.line_of_door_thickness = Line.CreateBound(options_for_create.start_point, end_point)
            else:
                options_for_create.line_of_door_thickness = Line.CreateBound(options_for_create.start_point,
                                                                             end_point).CreateReversed()
        return options_for_create

    def get_info_for_specified_line(self, plugin_options):
        '''
        Возвращает информацию для построения прямоугольного контура на толщину дверного проема, заданную пользователем
        plugin_options: настройки, которые выбрал пользователь в интерфейсе окна
        return: опции для построения прямоугольного контура дверного проема
        '''
        info_for_create = self.get_base_info_for_door_contour()
        distance_from_user = plugin_options.door_contour_offset
        start_point = info_for_create.start_point
        min_dist = 1  # мм для минимального расстояния
        if min_dist < float(distance_from_user) <= convert_to_millimeters_from_feet(info_for_create.distance):
            direction = info_for_create.line_of_door_thickness.Direction
            info_for_create.line_of_door_thickness = Line.CreateBound(start_point,
                                                                      start_point +
                                                                      direction *
                                                                      convert_from_millimeters_to_feet(
                                                                          distance_from_user))
            return info_for_create

    def check_door_z_location(self, plugin_options):
        '''
        Проверка соответствия положения перекрытия и дверного проема по z координате
        '''
        door_location_z = float(self.get_door_location(self.door).Z)
        room_level_point_z = doc.GetElement(self.room.LevelId).Elevation
        floor_z_point = float(room_level_point_z + convert_from_millimeters_to_feet(plugin_options.level_offset))
        res = True
        diff = convert_from_millimeters_to_feet(1000)  # разница между положением низа создаваемого перекрытия и двери
        if door_location_z > floor_z_point:
            if abs(door_location_z - floor_z_point) > diff:
                res = False
        return res

    def get_base_info_for_door_contour(self):
        '''
        Возвращает петлю кривых дверного проема, полученную из пересечения с линией, созданной из центра дверного проема
        вправо/влево
        plugin_options: настройки, выбранные пользователем в окне запуска скрипта
        return: петля кривых (CurveLoop()) дверного проема в форме прямоугольника
        '''

        info_for_create = DoorContourParams()

        # Создание линии из центра дверного проема вправо
        first_line, is_right = self.create_line_from_door(DirectionEnum.right)
        # Формирование виртуального Solid из всех стен (включая стену-основу), присоединенных к основе стены дверного
        # проема
        wall_solid = self.solid_operations.get_solid_from_host_walls(self.door)
        room_solid = self.room_contour.create_virtual_solid_of_room()

        boundary_point_in_door_center = self.get_boundary_point_from_room_in_door_center(room_solid)
        # Проверка на пересечение линии, запущенной вправо
        intersect_opt_inside = SolidCurveIntersectionOptions()
        intersect_opt_outside = SolidCurveIntersectionOptions()
        intersect_opt_outside.ResultType = SolidCurveIntersectionMode.CurveSegmentsOutside
        first_intersect = wall_solid.IntersectWithCurve(first_line, intersect_opt_inside)
        if first_intersect.SegmentCount < 1:
            # Если справа линия не пересекла Solid стен - создание линии по направлению влево от проема и повторная
            # проверка на пересечение
            first_line, is_right = self.create_line_from_door(DirectionEnum.left)
            first_intersect = wall_solid.IntersectWithCurve(first_line, intersect_opt_inside)

            if first_intersect.SegmentCount > 0:
                # Если линия, запущенная влево пересекла Solid стен - замена результата проверки на внешние кривые
                first_intersect = wall_solid.IntersectWithCurve(first_line, intersect_opt_outside)

        else:
            # Если линия, запущенная вправо пересекла Solid стен - замена результата проверки на внешние кривые
            first_intersect = wall_solid.IntersectWithCurve(first_line, intersect_opt_outside)
        # Получение линии, соответствующей половине ширины дверного проема из внешних сегментов кривых по результатам
        # проверки
        line_of_half_door_width = first_intersect.GetCurveSegment(0)

        # Получение координат пересечения Solid стен и линии
        intersect_coord = line_of_half_door_width.GetEndPoint(1)

        # Получение ширины проема
        info_for_create.door_width = line_of_half_door_width.Length * 2

        # Получение линии толщины проема
        line_of_door_thickness = self.get_door_thickness_line(wall_solid, intersect_coord, is_right)

        info_for_create.door_vector = self.get_vector_from_door(self.door)
        info_for_create.is_right = is_right
        info_for_create.start_point = self.get_start_point_for_door_contour(line_of_door_thickness,
                                                                            boundary_point_in_door_center)

        info_for_create.distance = convert_to_millimeters_from_feet(line_of_door_thickness.Length)
        info_for_create.line_of_door_thickness = self.check_line_of_door_thickness(line_of_door_thickness,
                                                                                   info_for_create.start_point)
        info_for_create.boundary_point_of_center_room = boundary_point_in_door_center

        return info_for_create

    def closest_point_to_target(self, target, points):
        min_distance = float("inf")
        closest = points[0]
        for point in points:
            distance = point.DistanceTo(target)
            if distance < min_distance:
                min_distance = distance
                closest = point
        return closest

    @staticmethod
    def get_door_location(door):
        try:
            return door.Location.Point
        except:
            return None

    @staticmethod
    def get_vector_from_door(door):
        door_normal = door.FacingOrientation.Normalize()
        return door_normal


def create_test_model_line(geom_line):
    dir = geom_line.Direction.Normalize()
    x = dir.X
    y = dir.Y
    z = dir.Z

    origin = geom_line.Origin
    normal = XYZ(z - y, x - z, y - x)
    plane = Plane.CreateByNormalAndOrigin(normal, origin)
    sketch = SketchPlane.Create(doc, plane)
    doc.Create.NewModelCurve(geom_line, sketch)


class SimplifyCurves:
    def __init__(self, curves_list):
        self.__curves_list = curves_list
        self.__simplified_curves = self.simplify()

    @staticmethod
    def are_join(curve, next_curve):
        '''
        Проверяет, соединен ли конец (XY) 1-й кривой и начало (XY) 2-й кривой
        curve: текущая кривая
        next_curve: следующая кривая
        return: True, если 2 кривые имеют общую точку соединения, иначе False
        '''

        x1, x2 = curve.GetEndPoint(1).X, next_curve.GetEndPoint(0).X
        diff_x = abs(x1 - x2)

        y1, y2 = curve.GetEndPoint(1).Y, next_curve.GetEndPoint(0).Y
        diff_y = abs(y1 - y2)

        are_join = diff_x < 0.01 and diff_y < 0.01

        return are_join

    @staticmethod
    def are_collinear(curve, next_curve):
        curve_vector = (curve.GetEndPoint(1) - curve.GetEndPoint(0)).Normalize()
        add_curve_vector = (next_curve.GetEndPoint(1) - next_curve.GetEndPoint(0)).Normalize()
        are_collinear = (isinstance(curve, Line) and isinstance(next_curve, Line)) and curve_vector.IsAlmostEqualTo(
            add_curve_vector)
        return are_collinear

    def append_curve(self, curve, next_curve):
        '''
        Создает одну прямую линию из двух, если они являются прямыми и коллинеарными и если конечная точка первой
        совпадает с начальной точкой второй
        curve: текущая кривая
        next_curve: следующая кривая
        return: True и новую кривую, если слияние кривых возможно и прошло успешно, иначе False и ту же самую кривую
        '''
        if curve is not None and next_curve is not None:
            are_collinear = self.are_collinear(curve, next_curve)
            are_join = self.are_join(curve, next_curve)
            if are_collinear and are_join:
                new_curve = Line.CreateBound(curve.GetEndPoint(0), next_curve.GetEndPoint(1))
                return True, new_curve
        return False, curve

    def simplify(self):
        '''
        Соединяет кривые у замкнутой петли (Loop), лежащие на одной прямой и возвращает новую упрощенную
        замкнутую петлю (Loop)
        return: Новая петля с оптимизированными кривыми, которые лежали на одной прямой друг за другом
        '''
        correct_curves = []
        curve_prev = None
        for i in range(len(self.__curves_list)):
            curve_current = self.__curves_list[i]
            (curve_added, curve_prev) = self.append_curve(curve_prev, curve_current)
            if curve_prev is None:
                curve_prev = curve_current
                continue
            if i != 0 and i != (len(self.__curves_list) - 1) and (not curve_added):
                correct_curves.append(curve_prev)
                curve_prev = curve_current
                continue
            if i == (len(self.__curves_list) - 1):
                if curve_added:
                    correct_curves.append(curve_prev)
                else:
                    correct_curves.append(curve_prev)
                    correct_curves.append(curve_current)
        if HOST_APP.is_newer_than(2021):
            simplified_curve_loop = CurveLoop()
        else:
            simplified_curve_loop = CurveArray()
        for curve in correct_curves:
            simplified_curve_loop.Append(curve)
        return simplified_curve_loop

    def simplified_curves(self):
        return self.__simplified_curves


class RoomWallsContour:
    def __init__(self, room, plugin_options):
        self.room = room
        self.revit_info = RevitRepository(doc)
        self.plugin_options = plugin_options

    def curve_arrays_into_curve_loops(self, curve_arrays):
        '''
        Создает список из замкнутых петель (CurveLoop()) из списка массива кривых (CurveArray()) для использования при
        создании виртуального Solid помещения для Revit 2020-2021
        curve_arrays: Список из массивов кривых
        return: список из CurveLoop()
        '''
        curve_loops = []
        for curve_array in curve_arrays:
            curve = CurveLoop()
            for loop in curve_array:
                curve.Append(loop)
            curve_loops.append(curve)

        return curve_loops

    def curve_loop_into_curve_array(self, curve_loop):
        curve_array = CurveArray()
        for curve in curve_loop:
            curve_array.Append(curve)
        return curve_array

    def create_virtual_solid_of_room(self, offset=0):
        '''
        Создает виртуальный Solid по контуру помещения со смещением наружу на указанное расстояние в мм
        offset: смещение контура Solid помещения наружу, в мм
        return: Виртуальный Solid помещения
        '''
        curve_loops = self.get_curve_loops_of_room_by_walls()
        room_height = self.room.UnboundedHeight
        new_curve_loops = []
        for curve_loop in curve_loops:
            new_curve_loop = curve_loop.CreateViaOffset(curve_loop, convert_from_millimeters_to_feet(offset),
                                                        XYZ(0, 0, 1))
            new_curve_loops.append(new_curve_loop)

        virtual_solid = GeometryCreationUtilities.CreateExtrusionGeometry(new_curve_loops, XYZ(0, 0, 1), room_height)
        return virtual_solid

    def correct_z_point_to_curve(self, curve):
        room_z_offset = self.room.BaseOffset
        room_level_elevation = doc.GetElement(self.room.LevelId).Elevation
        room_z_point = room_z_offset + room_level_elevation
        if isinstance(curve, Line):
            # Обработка линии
            start_point = curve.GetEndPoint(0)
            end_point = curve.GetEndPoint(1)
            new_start_point = XYZ(start_point.X, start_point.Y, room_z_point)
            new_end_point = XYZ(end_point.X, end_point.Y, room_z_point)
            return Line.CreateBound(new_start_point, new_end_point)

        elif isinstance(curve, Arc):
            # Обработка дуги
            center = curve.Center
            radius = curve.Radius
            start_angle = curve.GetEndParameter(0)
            end_angle = curve.GetEndParameter(1)
            new_center = XYZ(center.X, center.Y, room_z_point)
            return Arc.Create(new_center, radius, start_angle, end_angle, curve.GetEndPoint(0), curve.GetEndPoint(1))

    def get_curve_loops_of_room_by_walls(self):
        '''
        Возвращает список замкнутых петель (с упрощенными кривыми) из границ помещения
        '''
        spatial_element_boundary_options = SpatialElementBoundaryOptions()
        curve_loops = []
        loops = self.room.GetBoundarySegments(spatial_element_boundary_options)
        for loop in loops:
            curves = []
            for curve in loop:
                old_curve = curve.GetCurve()
                new_correct_curve = self.correct_z_point_to_curve(old_curve)
                curves.append(new_correct_curve)
            curve_loops.append(SimplifyCurves(curves).simplified_curves())
        curve_loops_with_offset = []
        inward_offset = convert_from_millimeters_to_feet(self.plugin_options.offset_into_room)
        for curve_loop in curve_loops:
            curve_loop_with_offset = self.create_curve_loop_offset_inward(curve_loop, inward_offset)
            curve_loops_with_offset.append(curve_loop_with_offset)
        if HOST_APP.is_newer_than(2021):
            return curve_loops_with_offset
        else:
            return self.curve_arrays_into_curve_loops(curve_loops_with_offset)

    def create_curve_loop_offset_inward(self, curve_loop, offset_distance):
        plane = curve_loop.GetPlane()
        normal = plane.Normal  # Нормаль плоскости границ помещения

        if not curve_loop.IsCounterclockwise(normal):
            # Если ориентация по часовой стрелке, инвертируем нормаль
            normal = -normal
        inward_offset_distance = -offset_distance

        offset_curve_loop = CurveLoop.CreateViaOffset(curve_loop, inward_offset_distance, normal)
        return offset_curve_loop

    def get_z_from_curve_loops(self, curve_loops):
        for curve_loop in curve_loops:
            for curve in curve_loop:
                return curve.GetEndPoint(1).Z

    def create_curve_loop_equal_to_Z(self, z, old_curve_loop):
        '''
        Создание новой петли кривых (CurveLoop()) из старой, но выравненных по z координате
        z: координата z, по которой нужно выровнять кривые.
        curve_list: старая петля кривых (CurveLoop()), которую нужно выровнять по z
        return: новая петля кривых, выровненная по z координате
        '''
        new_curve_loop = CurveLoop()
        for curve in old_curve_loop:
            old_start_x, old_start_y = curve.GetEndPoint(0).X, curve.GetEndPoint(0).Y
            old_end_x, old_end_y = curve.GetEndPoint(1).X, curve.GetEndPoint(1).Y
            start_point = XYZ(old_start_x, old_start_y, z)
            end_point = XYZ(old_end_x, old_end_y, z)
            equal_line = Line.CreateBound(start_point, end_point)
            new_curve_loop.Append(equal_line)
        return new_curve_loop

    def get_lower_curve_loops_from_solid(self, solid):
        for face in solid.Faces:
            if face.FaceNormal[2] == -1:
                return face.GetEdgesAsCurveLoops()


class RoomFloorContour:
    def __init__(self, room, plugin_options):
        self.room = room
        self.revit_info = RevitRepository(doc)
        self.plugin_options = plugin_options
        self.room_contour = RoomWallsContour(self.room, plugin_options)

    def get_curve_arrays_with_doors(self):
        '''
        Возвращает самый длинный массив кривых (ограничивающий контур) из границ помещения, а также список массивов
        кривых, если они есть внутри помещения (для Revit 2020-2021) с дверными проемами для построения отверстий
        внутри перекрытия
        return: Ограничивающий контур помещения; список из кривых для построения отверстий внутри перекрытия
        '''
        curve_loops = self.curve_loops_of_room_contour()
        curve_loops = sorted(curve_loops, key=lambda x: x.GetExactLength(), reverse=True)

        boundary_curve_array = self.room_contour.curve_loop_into_curve_array(curve_loops[0])
        curves_for_openings = [self.room_contour.curve_loop_into_curve_array(curve_loop) for curve_loop in
                               curve_loops[1:]]

        return boundary_curve_array, curves_for_openings

    def boundary_array_with_doors(self):
        return self.get_curve_arrays_with_doors()[0]

    def openings_arrays_with_doors(self):
        return self.get_curve_arrays_with_doors()[1]

    def curve_loops_of_room_contour(self):
        return self.get_curve_loops_with_doors()

    def get_doors_from_room(self):
        '''
        Возвращает список всех дверей, смещенные точки которых находятся внутри помещения
        '''

        all_doors = self.revit_info.all_doors_on_active_view
        doors_with_points = []
        error_doors_ids = []
        for door in all_doors:
            try:
                doors_with_points.append(DoorWithPoints(door))
            except:
                error_doors_ids.append(door.Id)
                continue
        doors_in_room = []
        for door_with_points in doors_with_points:
            points = door_with_points.points
            if points is None:
                continue
            for point in points:
                if self.room.IsPointInRoom(point):
                    doors_in_room.append(door_with_points.revit_door)
        return doors_in_room, error_doors_ids

    def get_curve_loops_with_doors(self):
        '''
        Создает новую петлю кривых (CurveLoop()) помещения с дверными проемами
        return: Возвращает новую петлю кривых с контурами дверных проемов
        '''

        room_curve_loops = self.room_contour.get_curve_loops_of_room_by_walls()
        doors = self.get_doors_from_room()[0]
        room_solid = GeometryCreationUtilities.CreateExtrusionGeometry(room_curve_loops, XYZ(0, 0, 1), 1)
        if len(doors) > 0:
            z = self.room_contour.get_z_from_curve_loops(room_curve_loops)
            for door in doors:
                try:
                    door_curve_loop = self.plugin_options.door_contour_option.create_contour(self.room, door,
                                                                                             self.plugin_options)
                    if door_curve_loop is None:
                        continue
                    door_curve_loop = self.room_contour.create_curve_loop_equal_to_Z(z, door_curve_loop)
                    door_solid = GeometryCreationUtilities.CreateExtrusionGeometry([door_curve_loop], XYZ(0, 0, 1),
                                                                                   1)
                    room_solid = BooleanOperationsUtils.ExecuteBooleanOperation(room_solid, door_solid,
                                                                                BooleanOperationsType.Union)
                except:
                    continue
        new_curve_loops = self.room_contour.get_lower_curve_loops_from_solid(room_solid)

        return new_curve_loops

    def get_curve_loops_from_room(self):
        '''
        Создает новую петлю кривых (CurveLoop()) помещения с дверными проемами
        return: Возвращает новую петлю кривых с контурами дверных проемов
        '''

        room_curve_loops = self.room_contour.get_curve_loops_of_room_by_walls()
        doors = self.get_doors_from_room()[0]
        room_solid = GeometryCreationUtilities.CreateExtrusionGeometry(room_curve_loops, XYZ(0, 0, 1), 1)
        if len(doors) > 0:
            z = self.room_contour.get_z_from_curve_loops(room_curve_loops)
            for door in doors:
                try:
                    door_curve_loop = self.plugin_options.door_contour_option.create_contour(self.room, door)
                    if door_curve_loop is None:
                        break
                    door_curve_loop = self.room_contour.create_curve_loop_equal_to_Z(z, door_curve_loop)
                    door_solid = GeometryCreationUtilities.CreateExtrusionGeometry([door_curve_loop], XYZ(0, 0, 1),
                                                                                   1)
                    room_solid = BooleanOperationsUtils.ExecuteBooleanOperation(room_solid, door_solid,
                                                                                BooleanOperationsType.Union)
                except:
                    continue
        new_curve_loops = self.room_contour.get_lower_curve_loops_from_solid(room_solid)

        return new_curve_loops

    def get_contour(self):
        if HOST_APP.is_older_than(2022):
            return self.boundary_array_with_doors()
        else:
            return self.curve_loops_of_room_contour()


class CreateFloorsByRooms:
    def __init__(self):
        pass

    def floor_create(self, room, plugin_options):
        '''
        Создает перекрытие на основе CurveLoop помещения и его уровня, заданным типоразмером перекрытия со смещением
        от уровня (опционально)
        room: помещение, на основе которого будет создано перекрытие
        plugin_options: настройки, выбранные пользователем в окне запуска скрипта
        return: текущее созданное перекрытие
        '''
        floor_type = plugin_options.floor_type
        level_offset = plugin_options.level_offset
        curves = RoomFloorContour(room, plugin_options).get_contour()
        if HOST_APP.is_older_than(2022):
            level = doc.GetElement(room.LevelId)
            current_floor = doc.Create.NewFloor(curves, floor_type, level, False)

        else:
            level_id = room.LevelId
            current_floor = Floor.Create(doc, curves, floor_type.Id, level_id)

        converted_level_offset = convert_from_millimeters_to_feet(level_offset)
        current_floor.SetParamValue(BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM, converted_level_offset)
        room_boundary_param = current_floor.get_Parameter(BuiltInParameter.WALL_ATTR_ROOM_BOUNDING)
        room_boundary_param.Set(False)

        return current_floor

    def openings_create(self, floor, curves):
        '''
        Создает элемент категории "Вырезание проема в перекрытии" для указанного перекрытия
        floor: перекрытие, в котором будет созданы отверстия
        curves: список кривых, по которым необходимо создать отверстия в перекрытие
        '''
        if len(curves) != 0:
            for curve in curves:
                doc.Create.NewOpening(floor, curve, True)

    def create_floors_by_rooms_on_view(self, rooms, plugin_options):
        '''
        Создает перекрытия последовательно по помещениям в выборке, используя функцию создания перекрытия по помещению
        Для Revit версии 2021 и старше создаются вырезания в перекрытии отдельной транзакцией, если контур помещения
        состоит из нескольких окружающих кривых
        rooms: список помещений, по контуру которых необходимо создать пол
        plugin_options: настройки, выбранные пользователем в окне запуска скрипта
        '''
        error_ids = []
        if HOST_APP.is_older_than(2022):
            with revit.Transaction("BIM: Создание перекрытий"):
                rooms_and_floors_dict = {}
                for room in rooms:
                    try:
                        floor = self.floor_create(room, plugin_options)
                        rooms_and_floors_dict[room] = floor
                    except:
                        error_ids.append(room.Id)

            with revit.Transaction("BIM: Создание отверстий в перекрытии"):
                for r, fl in rooms_and_floors_dict.items():
                    opening_curve_arrays = RoomFloorContour(room, plugin_options).openings_arrays_with_doors()
                    self.openings_create(fl, opening_curve_arrays)
        else:
            with revit.Transaction("BIM: Создание перекрытий"):
                for room in rooms:
                    try:
                        self.floor_create(room, plugin_options)
                    except:
                        error_ids.append(room.Id)
        if len(error_ids) > 0:
            show_error_message(error_ids)


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
        if not is_int(self.__view_model.level_offset) or not is_int(
                self.__view_model.door_contour_offset) or not is_int(self.__view_model.offset_into_room):
            self.__view_model.error_text = "Введите целое число"
            return False
        if int(self.__view_model.door_contour_offset) < 0 or int(self.__view_model.offset_into_room) < 0:
            self.__view_model.error_text = "Смещение должно быть положительным числом"
            return False
        self.__view_model.error_text = None
        return True

    def Execute(self, parameter):
        plugin_options = self.__view_model.get_config()

        if self.__view_model.is_checked_selected:
            # Если пользователь выбрал создать перекрытия по предварительно выбранным помещениям

            self.__create_floors_by_view.create_floors_by_rooms_on_view(self.__view_model.selected_rooms,
                                                                        plugin_options)

        elif self.__view_model.is_checked_select:
            # Если пользователь выбрал создать перекрытия по выбранным помещениям

            select_rooms = self.__revit_repository.select_rooms_on_view("Выберите помещения")
            self.__create_floors_by_view.create_floors_by_rooms_on_view(select_rooms, plugin_options)

        elif self.__view_model.is_checked_on_view:
            # Если пользователь выбрал создать перекрытия на активном виде

            self.__create_floors_by_view.create_floors_by_rooms_on_view(self.__view_model.rooms_on_active_view,
                                                                        plugin_options)


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
        if len(self.__selected_rooms) > 0:
            self.__is_already_enabled = True
            self.__is_checked_selected = True
            self.__is_checked_select = False
        else:
            self.__is_already_enabled = False

        self.__error_text = ""
        self.__create_floors_by_rooms = CreateFloorsByRoomsCommand(self)
        self.__doors_contours_options = [ContourNotCreate(), ContourCreateFullThickness(),
                                         ContourCreateToTheMiddle(), ContourCreateForSpecifiedLength()]
        self.__selected_door_contour_option = self.__doors_contours_options[0]
        self.__door_contour_offset = "0"
        self.__is_enabled_door_contour_offset = False
        self.__door_openings = [DoorOpeningInAnyDirection(), DoorOpeningInside(), DoorOpeningOutside()]
        self.__selected_door_opening = self.__door_openings[0]
        self.__offset_into_room = "0"

    @property
    def floor_types(self):
        return self.__floor_types

    @reactive
    def rooms_on_active_view(self):
        return self.__rooms_on_active_view

    @reactive
    def selected_door_opening(self):
        return self.__selected_door_opening

    @selected_door_opening.setter
    def selected_door_opening(self, value):
        self.__selected_door_opening = value

    @reactive
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
    def offset_into_room(self):
        return self.__offset_into_room

    @offset_into_room.setter
    def offset_into_room(self, value):
        self.__offset_into_room = value

    @reactive
    def is_checked_selected(self):
        return self.__is_checked_selected

    @is_checked_selected.setter
    def is_checked_selected(self, value):
        self.__is_checked_selected = value

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
    def is_already_enabled(self):
        return self.__is_already_enabled

    @reactive
    def selected_rooms(self):
        return self.__selected_rooms

    @reactive
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value

    @reactive
    def doors_contours_options(self):
        return self.__doors_contours_options

    @reactive
    def selected_door_contour_option(self):
        return self.__selected_door_contour_option

    @selected_door_contour_option.setter
    def selected_door_contour_option(self, value):
        if value == self.__doors_contours_options[len(self.__doors_contours_options) - 1]:
            self.is_enabled_door_contour_offset = True
        else:
            self.is_enabled_door_contour_offset = False
        self.__selected_door_contour_option = value

    @reactive
    def door_contour_offset(self):
        return self.__door_contour_offset

    @door_contour_offset.setter
    def door_contour_offset(self, value):
        self.__door_contour_offset = value

    @reactive
    def is_enabled_door_contour_offset(self):
        return self.__is_enabled_door_contour_offset

    @is_enabled_door_contour_offset.setter
    def is_enabled_door_contour_offset(self, value):
        if not value:
            self.door_contour_offset = "0"
        self.__is_enabled_door_contour_offset = value

    @property
    def door_openings(self):
        return self.__door_openings

    def get_config(self):
        plugin_config = PluginConfig()
        plugin_config.floor_type = self.__selected_floor_type
        plugin_config.level_offset = self.__level_offset
        plugin_config.door_contour_option = self.__selected_door_contour_option
        plugin_config.door_contour_offset = self.__door_contour_offset
        plugin_config.door_opening_option = self.__selected_door_opening
        plugin_config.offset_into_room = self.__offset_into_room
        return plugin_config


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
