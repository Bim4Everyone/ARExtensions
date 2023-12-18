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


def convert_to_value(value):
    if HOST_APP.is_older_than(2022):
        return UnitUtils.ConvertToInternalUnits(int(value), DisplayUnitType.DUT_MILLIMETERS)
    else:
        return UnitUtils.ConvertToInternalUnits(int(value), UnitTypeId.Millimeters)


def convert_from_value(value):
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


def line_for_check(line):
    with revit.Transaction("Test line"):
        doc.Create.NewDetailCurve(active_view, line)


def door_contour_options():
    dict = {0: "Не заводить контур пола в дверные проемы",
            1: "Заводить контур на всю толщины стены",
            2: "Заводить контур до середины стены",
            3: "Заводить контур на указанное значение, мм"}
    return dict


def selected_index_of_dict(value):
    door_options = door_contour_options()
    for k, v in door_options.items():
        if value == v:
            return k
    return 0


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

    # def create_virtual_solid_of_room(self, offset=0):
    #     '''
    #     Создает виртуальный Solid по контуру помещения со смещением наружу на указанное расстояние в мм
    #     return: Виртуальный Solid помещения
    #     '''
    #     curve_loops = self.get_curve_loops_of_room()
    #     max_length = 0
    #     boundary_curve = curve_loops[0]
    #     for curve_loop in curve_loops:
    #         current_length = curve_loop.GetExactLength()
    #         if current_length > max_length:
    #             max_length = current_length
    #             boundary_curve = curve_loop
    #     new_curve_loop = boundary_curve.CreateViaOffset(boundary_curve, convert_to_value(offset), XYZ(0, 0, 1))
    #     virtual_solid = GeometryCreationUtilities.CreateExtrusionGeometry([new_curve_loop], XYZ(0, 0, 1), 10)
    #     return virtual_solid
    def create_virtual_solid_of_room(self, offset=0):
        '''
        Создает виртуальный Solid по контуру помещения со смещением наружу на указанное расстояние в мм
        return: Виртуальный Solid помещения
        '''
        curve_loops = self.get_curve_loops_of_room()
        new_curve_loops = []
        for curve_loop in curve_loops:
            new_curve_loop = curve_loop.CreateViaOffset(curve_loop, convert_to_value(offset), XYZ(0, 0, 1))
            new_curve_loops.append(new_curve_loop)

        virtual_solid = GeometryCreationUtilities.CreateExtrusionGeometry(new_curve_loops, XYZ(0, 0, 1), 10)
        return virtual_solid

    def get_doors_from_room(self):
        '''
        Возвращает список всех дверей, которые пересекают виртуальный Solid помещения
        '''
        virtual_solid = self.create_virtual_solid_of_room(300)

        intersect_filter = ElementIntersectsSolidFilter(virtual_solid)
        doors = (FilteredElementCollector(doc, active_view.Id)
                 .WhereElementIsNotElementType()
                 .OfCategory(BuiltInCategory.OST_Doors)
                 .WherePasses(intersect_filter))
        list_doors = elements_to_list(doors)
        return list_doors

    def get_door_location(self, door):
        return door.Location.Point

    # def closest_point_xyz(self, target, point, min_distance=float('inf')):
    #     '''
    #     Возвращает минимальную дистанцию и ближайшую точку к целевой точке
    #     target: целевая точка, для которой нужно вычислить минимальную дистанцию и ближайшую точку
    #     point: проверяемая точка, для которой будет выполняться проверка минимальной дистанции до целевой точки
    #     min_distance: минимальное расстояние, переданное в функцию для проверки расстояния до целевой точки
    #     return: минимальное расстояние до целевой точки, ближайшая точка к целевой точке
    #     '''
    #     distance = (point[0] - target[0]) ** 2 + (point[1] - target[1]) ** 2 + (point[2] - target[2]) ** 2
    #     closest = target
    #     if distance < min_distance:
    #         closest = point
    #         min_distance = distance
    #     return min_distance, closest

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
        Возвращает объединенный Solid из стен, которые присоединены к основе стены двери
        door: дверь, из которой будет взята основа стена
        return: объединенный Solid из стен, которые присоединены к основе стены двери
        '''
        opt = Options()
        opt.DetailLevel = ViewDetailLevel.Fine
        wall = door.Host
        host_solid = self.get_solid_from_element(wall)
        joined_elementIds = JoinGeometryUtils.GetJoinedElements(doc, wall)
        joined_elements = [doc.GetElement(wall) for wall in joined_elementIds]
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

    def get_vector_from_door(self, door):
        door_normal = door.FacingOrientation.Normalize()
        return door_normal

    def create_line_from_door(self, door, mode="right"):
        '''
        Создает линию из центра дверного проема, поднятую на определенное расстояние, в сторону стен (вправо или влево
        от проема) с длиной равной константе, в мм
        door: целевая дверь, из центра которой будет создана линия
        mode: режим создания линии - вправо или влево от центра дверного проема ("right"/"left")
        return: линия, созданная из центра дверного проема, направление линии - True, если линия вправо, False - влево
        '''
        door_location = self.get_door_location(door)
        door_vector = self.get_vector_from_door(door)
        normal_vector = XYZ.BasisZ.CrossProduct(door_vector).Normalize()
        z = convert_to_value(200)
        dist_const_left_right = convert_to_value(6000)
        dist_const_top_bottom = convert_to_value(500)
        start_point = XYZ(door_location[0], door_location[1], z)
        is_right = True

        end_point = XYZ(door_location[0], door_location[1], z) + normal_vector * dist_const_left_right
        if mode == "left":
            end_point = XYZ(door_location[0], door_location[1], z) - normal_vector * dist_const_left_right
            is_right = False
        if mode == "top":
            end_point = XYZ(door_location[0], door_location[1], z) + door_vector * dist_const_top_bottom
        if mode == "bottom":
            end_point = XYZ(door_location[0], door_location[1], z) - door_vector * dist_const_top_bottom
            is_right = False
        line = Line.CreateBound(start_point, end_point)
        return line, is_right

    def create_line_from_xyz(self, door, point, is_right=True):
        '''
        Создает линию, перпендикулярную ширине проема, из указанной точки, равной константе, в мм
        door: целевая дверь, у которой будет взят вектор направления
        point: точка, которая будет являться центром создаваемой линии
        mode: режим построения линии ("right"/"left"), в зависимости от этого, будет меняться направление
        построения линии
        return: линия, созданная перпендикулярно ширине проема
        '''
        dist_const = convert_to_value(1000)
        door_vector = self.get_vector_from_door(door)
        start_point = point + door_vector * dist_const
        end_point = point - door_vector * dist_const
        if not is_right:
            start_point = point - door_vector * dist_const
            end_point = point + door_vector * dist_const
        line = Line.CreateBound(start_point, end_point)
        return line

    def create_one_line_from_two_segments(self, prev_line, current_line):
        '''
        Создает новую линию из начальных точек предыдущей линии и конечных текущей линии
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

    def create_rectangle_door_curve_loop(self, is_right, door_normal, rectangle_width, short_line):
        '''
        Создает петлю кривых контура дверного проема, начинающегося из короткой линии, обозначающую толщину проема
        is_right: bool направления создания до этого линии из центра проема (True - вправо, False - влево)
        door: целевая дверь, у которой будет взят вектор направления для построения линий
        door_width: ширина дверного проема
        short_line: короткая линия, обозначающая толщину проема и построенная по грани стены внутри дверного проема
        return: петля кривых (CurveLoop()) дверного проема в форме прямоугольника
        '''

        alongside_vector = XYZ.BasisZ.CrossProduct(door_normal).Normalize()
        start_point = short_line.GetEndPoint(1)

        res_curve_loop = CurveLoop()
        rectangle_width = -rectangle_width
        if is_right:
            alongside_vector = -alongside_vector

        end_point = start_point + alongside_vector * abs(rectangle_width)

        long_line = Line.CreateBound(start_point, end_point)

        second_short_line = Line.CreateBound(long_line.GetEndPoint(1),
                                             short_line.GetEndPoint(0) + alongside_vector * abs(rectangle_width))

        second_long_line = Line.CreateBound(second_short_line.GetEndPoint(1), short_line.GetEndPoint(0))

        # Последовательное создание петли кривых из линий
        res_curve_loop.Append(short_line)

        res_curve_loop.Append(long_line)

        res_curve_loop.Append(second_short_line)

        res_curve_loop.Append(second_long_line)

        return res_curve_loop

    def get_boundary_point_from_room_in_door_center(self, door, room_solid):
        line, is_right = self.create_line_from_door(door, "top")
        intersect_opt_inside = SolidCurveIntersectionOptions()
        intersect_opt_outside = SolidCurveIntersectionOptions()
        intersect_opt_outside.ResultType = SolidCurveIntersectionMode.CurveSegmentsOutside
        intersect = room_solid.IntersectWithCurve(line, intersect_opt_inside)
        if intersect.SegmentCount < 1:
            # Если линия, запущенная вверх не пересекла Solid помещения - создание линии по направлению вниз от проема
            # и повторная проверка на пересечение
            line, is_right = self.create_line_from_door(door, "bottom")
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

    def get_distance_from_two_points(self, point_a, point_b):
        distance = ((point_a.X - point_b.X) ** 2 + (point_a.Y - point_b.Y) ** 2) ** 0.5
        return distance

    def get_door_curve_loop(self, door, mode=1, distance_from_user=0):
        '''
        Возвращает петлю кривых дверного проема, полученную из пересечения с линией, созданной из центра дверного проема
        вправо/влево
        door: целевая дверь, по габаритам которой будет создана петля кривых (CurveLoop())
        return: петля кривых (CurveLoop()) дверного проема в форме прямоугольника
        '''
        # Создание линии из центра дверного проема вправо
        first_line, is_right = self.create_line_from_door(door)
        # Формирование виртуального Solid из всех стен (включая стену-основу), присоединенных к основе стены дверного
        # проема
        wall_solid = self.get_solid_from_host_walls(door)
        room_solid = self.create_virtual_solid_of_room()
        boundary_point_in_door_center = self.get_boundary_point_from_room_in_door_center(door, room_solid)

        # Проверка на пересечение линии, запущенной вправо
        intersect_opt_inside = SolidCurveIntersectionOptions()
        intersect_opt_outside = SolidCurveIntersectionOptions()
        intersect_opt_outside.ResultType = SolidCurveIntersectionMode.CurveSegmentsOutside

        first_intersect = wall_solid.IntersectWithCurve(first_line, intersect_opt_inside)
        if first_intersect.SegmentCount < 1:
            # Если справа линия не пересекла Solid стен - создание линии по направлению влево от проема и повторная
            # проверка на пересечение
            first_line, is_right = self.create_line_from_door(door, "left")
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
        door_width = line_of_half_door_width.Length * 2

        # Создание линии, перпендикулярной линии, полученной из результата первого пересечения
        second_line = self.create_line_from_xyz(door, intersect_coord, is_right)

        # Получение линии, соответствующей толщине дверного проема при помощи проверки на пересечение с Solid стен
        intersect_opt_inside = SolidCurveIntersectionOptions()
        second_intersect = wall_solid.IntersectWithCurve(second_line, intersect_opt_inside)
        line_of_door_thickness = second_intersect.GetCurveSegment(0)

        # Упрощение до 1 линии, если сегментов более 1
        if second_intersect.SegmentCount > 1:
            line_of_door_thickness = self.create_new_line_from_segments(second_intersect)

        door_vector = self.get_vector_from_door(door)

        points = []
        check_start_point = line_of_door_thickness.GetEndPoint(0)
        points.append(check_start_point)
        check_end_point = line_of_door_thickness.GetEndPoint(1)
        points.append(check_end_point)
        start_point = self.closest_point_to_target(boundary_point_in_door_center, points)
        if start_point == check_end_point:
            line_of_door_thickness = line_of_door_thickness.CreateReversed()
        if mode == 2:
            distance = convert_from_value(self.get_distance_from_two_points(check_start_point, check_end_point))
            if distance > 2:
                end_point = line_of_door_thickness.Evaluate(0.5, True)
                if is_right:
                    line_of_door_thickness = Line.CreateBound(start_point, end_point)
                else:
                    line_of_door_thickness = Line.CreateBound(start_point, end_point).CreateReversed()
        elif mode == 3:

            if 1 < float(distance_from_user) < convert_from_value(line_of_door_thickness.Length):
                percents = int(distance_from_user) / convert_from_value(line_of_door_thickness.Length)
                end_point = line_of_door_thickness.Evaluate(percents, True)
                line_of_door_thickness = Line.CreateBound(start_point, end_point)
                doc.Create.NewDetailCurve(active_view, line_of_door_thickness)
            else:
                return None

                # Создание петли кривых по исходным данным, полученным из результатов пересечения
        door_curve_loop = self.create_rectangle_door_curve_loop(is_right, door_vector, door_width,
                                                                line_of_door_thickness)
        return door_curve_loop

    # def get_boundary_curve_from_room(self, curve_loops):
    #     max_length = 0
    #     boundary_curve = curve_loops[0]
    #     for curve_loop in curve_loops:
    #         current_length = curve_loop.GetExactLength
    #         if current_length > max_length:
    #             max_length = current_length
    #     return boundary_curve

    def get_z_from_curve_loops(self, curve_loops):
        for curve_loop in curve_loops:
            for curve in curve_loop:
                return curve.GetEndPoint(1).Z

    def create_curve_loop_equal_to_Z(self, z, old_curve_loop):
        '''
        Создание новой петли кривых (CurveLoop()) из старой, но выравненных по z координате
        z: координата z, по которой нужно выровнять кривые
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

    def closest_point_to_target(self, target, points):
        min_distance = float("inf")
        closest = points[0]
        for point in points:
            distance = (point.X - target.X) ** 2 + (point.Y - target.Y) ** 2
            if distance < min_distance:
                min_distance = distance
                closest = point
        return closest

    def get_lower_curve_loop_from_solid(self, solid):
        for face in solid.Faces:
            if face.FaceNormal[2] == -1:
                return face.GetEdgesAsCurveLoops()

    def get_curve_loop_with_doors(self, mode=1, distance_from_user=0):
        '''
        Создает новую петлю кривых (CurveLoop()) помещения с дверными проемами
        '''

        room_curve_loops = self.get_curve_loops_of_room()
        doors = self.get_doors_from_room()

        room_solid = GeometryCreationUtilities.CreateExtrusionGeometry(room_curve_loops, XYZ(0, 0, 1), 1)
        # direct_shape = DirectShape.CreateElement(doc, ElementId(BuiltInCategory.OST_GenericModel))
        if len(doors) > 0:
            z = self.get_z_from_curve_loops(room_curve_loops)
            for door in doors:
                door_curve_loop = self.get_door_curve_loop(door, mode, distance_from_user)
                if door_curve_loop != None:
                    door_curve_loop = self.create_curve_loop_equal_to_Z(z, door_curve_loop)
                    door_solid = GeometryCreationUtilities.CreateExtrusionGeometry([door_curve_loop], XYZ(0, 0, 1), 1)

                    room_solid = BooleanOperationsUtils.ExecuteBooleanOperation(room_solid, door_solid,
                                                                                BooleanOperationsType.Union)
        new_curve_loops = self.get_lower_curve_loop_from_solid(room_solid)

        return new_curve_loops


class CreateFloorsByRooms:

    def floor_create(self, room, floor_type, mode, distance_from_user=0, level_offset=0):
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
            if mode > 0:
                curve_loops = RoomContour(room).get_curve_loop_with_doors(mode, distance_from_user)
            level_id = room.LevelId
            current_floor = Floor.Create(doc, curve_loops, floor_type.Id, level_id)

        converted_level_offset = convert_to_value(level_offset)
        current_floor.SetParamValue(BuiltInParameter.FLOOR_HEIGHTABOVELEVEL_PARAM, converted_level_offset)

        return current_floor

    def openings_create(self, floor, curves):
        '''
        Создает элемент категории "Вырезание проема в перекрытии" для указанного перекрытия
        '''
        if len(curves) != 0:
            for curve in curves:
                doc.Create.NewOpening(floor, curve, True)

    def create_floors_by_rooms_on_view(self, rooms, floor_type, mode, distance_from_user=0, level_offset=0):
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
                    floor = self.floor_create(room, floor_type, mode, distance_from_user, level_offset)
                    rooms_and_floors_dict[room] = floor

            with revit.Transaction("BIM: Создание отверстий в перекрытии"):
                for r, fl in rooms_and_floors_dict.items():
                    opening_curve_arrays = RoomContour(r).get_curve_arrays_of_room()[1]
                    self.openings_create(fl, opening_curve_arrays)
        else:
            with revit.Transaction("BIM: Создание перекрытий"):
                for room in rooms:
                    self.floor_create(room, floor_type, mode, distance_from_user, level_offset)


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
        if not is_int(self.__view_model.level_offset) or not is_int(self.__view_model.door_contour_offset):
            self.__view_model.error_text = "Введите целое число"
            return False
        if int(self.__view_model.door_contour_offset) < 0:
            self.__view_model.error_text = "Смещение должно быть положительным числом"
            return False
        self.__view_model.error_text = None
        return True

    def Execute(self, parameter):
        if self.__view_model.is_checked_selected:
            # Если пользователь выбрал создать перекрытия по предварительно выбранным помещениям
            # with revit.Transaction("Test"):
            #     for room in self.__view_model.selected_rooms:
            #         RoomContour(room).get_curve_loop_with_doors()
            # try:
            #     RoomContour(room).create_new_curve_loop()
            # except:
            #     print("Не удалось обработать следующие помещения: " + str(room.Id))

            # RoomContour(self.__view_model.selected_rooms[0]).create_new_curve_loop()

            self.__create_floors_by_view.create_floors_by_rooms_on_view(self.__view_model.selected_rooms,
                                                                        self.__view_model.selected_floor_type,
                                                                        selected_index_of_dict(
                                                                            self.__view_model
                                                                            .selected_door_contour_option),
                                                                        self.__view_model.door_contour_offset,
                                                                        self.__view_model.level_offset)

        elif self.__view_model.is_checked_select:
            # Если пользователь выбрал создать перекрытия по выбранным помещениям

            select_rooms = self.__revit_repository.select_rooms_on_view("Выберите помещения")
            self.__create_floors_by_view.create_floors_by_rooms_on_view(select_rooms,
                                                                        self.__view_model.selected_floor_type,
                                                                        selected_index_of_dict(
                                                                            self.__view_model
                                                                            .selected_door_contour_option),
                                                                        self.__view_model.door_contour_offset,
                                                                        self.__view_model.level_offset)

        elif self.__view_model.is_checked_on_view:
            # Если пользователь выбрал создать перекрытия на активном виде

            self.__create_floors_by_view.create_floors_by_rooms_on_view(self.__view_model.rooms_on_active_view,
                                                                        self.__view_model.selected_floor_type,
                                                                        selected_index_of_dict(
                                                                            self.__view_model
                                                                            .selected_door_contour_option),
                                                                        self.__view_model.door_contour_offset,
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
        self.__doors_contours_options = door_contour_options().values()
        self.__selected_door_contour_option = self.doors_contours_options[0]
        self.__door_contour_offset = "0"
        self.__is_enabled_door_contour_offset = False

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
