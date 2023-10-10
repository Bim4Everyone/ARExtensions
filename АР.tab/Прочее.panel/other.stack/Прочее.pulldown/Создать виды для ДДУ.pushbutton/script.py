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


BUILDING_NUMBER = "ФОП_Секция СМР"
SECTION_NUMBER = "обр_ФОП_Раздел проекта"
CONSTR_GROUP = "обр_ФОП_Группа КР"
FILTRATION_1 = "обр_ФОП_Фильтрация 1"
FILTRATION_2 = "обр_ФОП_Фильтрация 2"
FORM_NUMBER = "обр_ФОП_Форма_номер"
VOLUME = "Объем"

AMOUNT = "Количество"
AMOUNT_SHARED_PARAM = "обр_ФОП_Количество"
AMOUNT_ON_LEVEL = "обр_ФОП_Количество типовых на этаже"
AMOUNT_OF_LEVELS = "обр_ФОП_Количество типовых этажей"
REBAR_DIAMETER = "мод_ФОП_Диаметр"
REBAR_LENGTH = "обр_ФОП_Длина"
REBAR_CALC_METERS = "обр_ФОП_Расчет в погонных метрах"
REBAR_MASS_PER_LENGTH = "обр_ФОП_Масса на единицу длины"
ROD_LENGTH = "Полная длина стержня"
IFC_FAMILY = "мод_ФОП_IFC семейство"

THICKNESS = "Толщина"
LENGTH = "Длина"
HEIGHT_ADSK = "ADSK_Размер_Высота"
WIDTH_ADSK = "ADSK_Размер_Ширина"
CONCRETE_MARK = "обр_ФОП_Марка бетона B"
BUILDING_INFO = "Наименование здания"


class RevitRepository:
    """
    This class created for collecting, checking and filtering elements from revit document.
    The class collects all elements of required categories.
    The class has methods to check availability of parameters and their values.
    The class has methods to filter elements by rules and table type.
    """
    def __init__(self, doc):
        self.doc = doc

        self.categories = []
        self.type_key_word = []
        self.quality_indexes = []

        self.__rebar = self.__get_all_rebar()
        self.__concrete = self.__get_all_concrete()
        self.__concrete_by_table_type = []
        self.__buildings = []
        self.__construction_sections = []
        self.__errors_dict = dict()

    def set_table_type(self, table_type):
        self.categories = table_type.categories
        self.type_key_word = table_type.type_key_word
        self.quality_indexes = table_type.indexes_info

        self.__get_concrete_by_table_type()
        self.__buildings = self.__get_elements_sections(BUILDING_NUMBER)
        self.__construction_sections = self.__get_elements_sections(SECTION_NUMBER)

    def check_exist_main_parameters(self):
        self.__errors_dict = dict()
        common_parameters = [SECTION_NUMBER,
                             BUILDING_NUMBER,
                             FILTRATION_1,
                             FILTRATION_2]
        concrete_inst_parameters = [VOLUME]
        rebar_inst_type_parameters = [FORM_NUMBER]
        concrete_common_parameters = common_parameters + concrete_inst_parameters

        for element in self.__rebar:
            element_type = self.doc.GetElement(element.GetTypeId())
            for parameter_name in common_parameters:
                if not element.IsExistsParam(parameter_name):
                    self.__add_error("Арматура___Отсутствует параметр у экземпляра___", element, parameter_name)

            for parameter_name in rebar_inst_type_parameters:
                if not element.IsExistsParam(parameter_name) and not element_type.IsExistsParam(parameter_name):
                    self.__add_error("Арматура___Отсутствует параметр у экземпляра или типоразмера___", element, parameter_name)

        for element in self.__concrete:
            for parameter_name in concrete_common_parameters:
                if not element.IsExistsParam(parameter_name):
                    self.__add_error("Железобетон___Отсутствует параметр у экземпляра___", element, parameter_name)

        if self.__errors_dict:
            missing_parameters = self.__create_error_list(self.__errors_dict)
            return missing_parameters

    def check_exist_rebar_parameters(self):
        self.__errors_dict = dict()
        rebar_inst_parameters = [CONSTR_GROUP,
                                 AMOUNT_ON_LEVEL,
                                 AMOUNT_OF_LEVELS]
        rebar_uniform_length_parameter = [REBAR_LENGTH]
        rebar_vary_length_parameter = [ROD_LENGTH]
        rebar_type_parameters = [IFC_FAMILY]
        rebar_inst_type_parameters = [REBAR_DIAMETER,
                                      REBAR_CALC_METERS]
        rebar_inst_type_by_number_parameters = [REBAR_MASS_PER_LENGTH]

        for element in self.__rebar:
            element_type = self.doc.GetElement(element.GetTypeId())
            for parameter_name in rebar_inst_parameters:
                if not element.IsExistsParam(parameter_name):
                    self.__add_error("Арматура___Отсутствует параметр у экземпляра___", element, parameter_name)

            for parameter_name in rebar_uniform_length_parameter:
                if hasattr(element, "DistributionType"):
                    if element.DistributionType == DB.Structure.DistributionType.Uniform:
                        if not element.IsExistsParam(parameter_name):
                            self.__add_error("Арматура___Отсутствует параметр у экземпляра___", element, parameter_name)
                elif not element.IsExistsParam(parameter_name):
                    self.__add_error("Арматура___Отсутствует параметр у экземпляра___", element, parameter_name)

            for parameter_name in rebar_vary_length_parameter:
                if hasattr(element, "DistributionType"):
                    if element.DistributionType == DB.Structure.DistributionType.VaryingLength:
                        if not element.IsExistsParam(parameter_name):
                            self.__add_error("Арматура___Отсутствует параметр у экземпляра___", element, parameter_name)

            for parameter_name in rebar_type_parameters:
                if not element_type.IsExistsParam(parameter_name):
                    self.__add_error("Арматура___Отсутствует параметр у типоразмера___", element, parameter_name)

            for parameter_name in rebar_inst_type_parameters:
                if not element.IsExistsParam(parameter_name) and not element_type.IsExistsParam(parameter_name):
                    self.__add_error("Арматура___Отсутствует параметр у экземпляра или типоразмера___", element, parameter_name)

            for parameter_name in rebar_inst_type_by_number_parameters:
                if element.IsExistsParam(FORM_NUMBER):
                    number_value = element.GetParamValue(FORM_NUMBER)
                elif element_type.IsExistsParam(FORM_NUMBER):
                    number_value = element_type.GetParamValue(FORM_NUMBER)

                if number_value >= 200:
                    if not element.IsExistsParam(parameter_name) and not element_type.IsExistsParam(parameter_name):
                        self.__add_error("Арматура___Отсутствует параметр у экземпляра или типоразмера___", element, parameter_name)

            if not element.IsExistsParam(AMOUNT_SHARED_PARAM) and not element.IsExistsParam(AMOUNT):
                self.__add_error("Арматура___Отсутствует параметр___", element, "{0} (для IFC - '{1}')".format(AMOUNT, AMOUNT_SHARED_PARAM))

        if self.__errors_dict:
            missing_parameters = self.__create_error_list(self.__errors_dict)
            return missing_parameters

    def check_parameters_values(self):
        self.__errors_dict = dict()
        concrete_inst_parameters = [VOLUME]
        rebar_inst_parameters = [AMOUNT_ON_LEVEL,
                                 AMOUNT_OF_LEVELS]
        rebar_uniform_length_parameter = [REBAR_LENGTH]
        rebar_vary_length_parameter = [ROD_LENGTH]
        rebar_inst_type_parameters = [REBAR_CALC_METERS]
        rebar_inst_type_diameter_parameters = [REBAR_DIAMETER]
        rebar_inst_type_by_number_parameters = [REBAR_MASS_PER_LENGTH]

        for element in self.__rebar:
            element_type = self.doc.GetElement(element.GetTypeId())
            for parameter_name in rebar_inst_parameters:
                if not element.GetParam(parameter_name).HasValue or element.GetParamValue(parameter_name) == None:
                    self.__add_error("Арматура___Отсутствует значение у параметра___", element, parameter_name)

            for parameter_name in rebar_uniform_length_parameter:
                if hasattr(element, "DistributionType"):
                    if element.DistributionType == DB.Structure.DistributionType.Uniform:
                        if not element.GetParam(parameter_name).HasValue or element.GetParamValue(parameter_name) == None:
                            self.__add_error("Арматура___Отсутствует значение у параметра___", element, parameter_name)
                elif not element.GetParam(parameter_name).HasValue or element.GetParamValue(parameter_name) == None:
                    self.__add_error("Арматура___Отсутствует значение у параметра___", element, parameter_name)

            for parameter_name in rebar_vary_length_parameter:
                if hasattr(element, "DistributionType"):
                    if element.DistributionType == DB.Structure.DistributionType.VaryingLength:
                        if not element.GetParam(parameter_name).HasValue:
                            self.__add_error("Арматура___Отсутствует значение у параметра___", element, parameter_name)

            for parameter_name in rebar_inst_type_parameters:
                if element.IsExistsParam(parameter_name):
                    if not element.GetParam(parameter_name).HasValue:
                        self.__add_error("Арматура___Отсутствует значение у параметра (экземпляра или типа)___", element, parameter_name)
                else:
                    if not element_type.GetParam(parameter_name).HasValue:
                        self.__add_error("Арматура___Отсутствует значение у параметра (экземпляра или типа)___", element, parameter_name)

            for parameter_name in rebar_inst_type_diameter_parameters:
                if element.IsExistsParam(FORM_NUMBER):
                    form_number = element.GetParamValueOrDefault(FORM_NUMBER)
                else:
                    form_number = element_type.GetParamValueOrDefault(FORM_NUMBER)

                if form_number < 200:
                    if element.IsExistsParam(parameter_name):
                        if not element.GetParam(parameter_name).HasValue or element.GetParamValue(parameter_name) == None:
                            self.__add_error("Арматура___Отсутствует значение у параметра (экземпляра или типа)___",
                                             element, parameter_name)
                    else:
                        if not element_type.GetParam(parameter_name).HasValue or element_type.GetParamValue(parameter_name) == None:
                            self.__add_error("Арматура___Отсутствует значение у параметра (экземпляра или типа)___",
                                             element, parameter_name)

            for parameter_name in rebar_inst_type_by_number_parameters:
                if element.IsExistsParam(FORM_NUMBER):
                    number_value = element.GetParamValue(FORM_NUMBER)
                elif element_type.IsExistsParam(FORM_NUMBER):
                    number_value = element_type.GetParamValue(FORM_NUMBER)

                if number_value >= 200:
                    if element.IsExistsParam(parameter_name):
                        if not element.GetParam(parameter_name).HasValue or element.GetParamValue(parameter_name) == None:
                            self.__add_error("Арматура___Отсутствует значение у параметра (экземпляра или типа)___", element, parameter_name)
                    else:
                        if not element_type.GetParam(parameter_name).HasValue or element_type.GetParamValue(parameter_name) == None:
                            self.__add_error("Арматура___Отсутствует значение у параметра (экземпляра или типа)___", element, parameter_name)

            if element_type.GetParamValue(IFC_FAMILY):
                if not element.GetParam(AMOUNT_SHARED_PARAM).HasValue:
                    self.__add_error("Арматура___Отсутствует значение у параметра___", element, AMOUNT_SHARED_PARAM)
            else:
                if not element.GetParam(AMOUNT).HasValue:
                    self.__add_error("Арматура___Отсутствует значение у параметра___", element, AMOUNT)

        for element in self.__concrete:
            for parameter_name in concrete_inst_parameters:
                if element.GetParamValue(parameter_name) == 0:
                    self.__add_error("Железобетон___Отсутствует значение у параметра___", element, parameter_name)

        if self.__errors_dict:
            empty_parameters = self.__create_error_list(self.__errors_dict)
            return empty_parameters



    def check_filtered_rebar(self, rebar):
        self.__errors_dict = dict()
        rebar_inst_parameters = [CONSTR_GROUP]

        for element in rebar:
            for parameter_name in rebar_inst_parameters:
                if not element.GetParam(parameter_name).HasValue or element.GetParamValue(parameter_name) == None:
                    self.__add_error("Арматура___Отсутствует значение у параметра___", element, parameter_name)

        if self.__errors_dict:
            empty_parameters = self.__create_error_list(self.__errors_dict)
            return empty_parameters

    def filter_by_main_parameters(self):
        filter_value = "Исключить из показателей качества"

        self.__rebar = self.__filter_by_param(self.__rebar, FILTRATION_1, filter_value, False)
        self.__rebar = self.__filter_by_param(self.__rebar, FILTRATION_2, filter_value, False)
        self.__rebar = self.__filter_by_param(self.__rebar, FORM_NUMBER, 1000, False)

        self.__concrete = self.__filter_by_param(self.__concrete, FILTRATION_1, filter_value, False)
        self.__concrete = self.__filter_by_param(self.__concrete, FILTRATION_2, filter_value, False)

    def __get_all_concrete(self):
        all_categories = [BuiltInCategory.OST_Walls,
                          BuiltInCategory.OST_StructuralColumns,
                          BuiltInCategory.OST_StructuralFoundation,
                          BuiltInCategory.OST_Floors,
                          BuiltInCategory.OST_StructuralFraming]
        categories_typed = List[BuiltInCategory]()
        for category in all_categories:
            categories_typed.Add(category)
        multi_cat_filter = ElementMulticategoryFilter(categories_typed)
        elements = FilteredElementCollector(self.doc).WherePasses(multi_cat_filter)
        elements.WhereElementIsNotElementType()
        return elements

    def __get_all_rebar(self):
        elements = FilteredElementCollector(self.doc).OfCategory(BuiltInCategory.OST_Rebar)
        elements.WhereElementIsNotElementType().ToElements()
        return elements

    def __get_concrete_by_table_type(self):
        categories_id = [x.Id for x in self.categories]
        filtered_concrete = [x for x in self.__concrete if x.Category.Id in categories_id]
        self.__concrete_by_table_type = self.__filter_by_type(filtered_concrete)

    def get_filtered_concrete_by_user(self, buildings, constr_sections):
        buildings = [x.text_value for x in buildings]
        constr_sections = [x.text_value for x in constr_sections]
        filtered_elements = []
        for element in self.concrete:
            if element.GetParamValue(BUILDING_NUMBER) in buildings:
                if element.GetParamValue(SECTION_NUMBER) in constr_sections:
                    filtered_elements.append(element)
        return filtered_elements

    def get_filtered_rebar_by_blds_and_scts(self, buildings, constr_sections):
        buildings = [x.text_value for x in buildings]
        constr_sections = [x.text_value for x in constr_sections]
        filtered_elements = []
        for element in self.rebar:
            if element.GetParamValue(BUILDING_NUMBER) in buildings:
                if element.GetParamValue(SECTION_NUMBER) in constr_sections:
                    filtered_elements.append(element)
        return filtered_elements

    def get_filtered_rebar_by_table_type(self, rebar):
        rebar_by_table_type = []
        rebar_group_values = [x.rebar_group for x in self.quality_indexes if x.index_type == "mass"]
        rebar_group_values = [name for group in rebar_group_values for name in group]
        for value in rebar_group_values:
            rebar_by_table_type += self.__filter_by_param(rebar, CONSTR_GROUP, value)
        return rebar_by_table_type

    def __filter_by_param(self, elements, param_name, value, is_include=True):
        filtered_list = []
        for element in elements:
            if element.IsExistsParam(param_name):
                param_value = element.GetParamValue(param_name)
            else:
                element_type = self.doc.GetElement(element.GetTypeId())
                param_value = element_type.GetParamValueOrDefault(param_name, 0)

            if (param_value == value) == is_include:
                filtered_list.append(element)
        return filtered_list

    def __filter_by_type(self, elements):
        filtered_list = []
        for element in elements:
            for word in self.type_key_word:
                if word in element.Name:
                    filtered_list.append(element)
        return filtered_list

    def __add_error(self, error_text, element, parameter_name):
        key = error_text + parameter_name
        self.__errors_dict.setdefault(key, [])
        self.__errors_dict[key].append(str(element.Id))

    def __create_error_list(self, errors_dict):
        missing_parameters = []
        for error in errors_dict.keys():
            error_info = []
            for word in error.split("___"):
                error_info.append(word)
            error_info.append(", ".join(errors_dict[error]))
            missing_parameters.append(error_info)

        # Attention! Unknown error found!

        # An issue was found when creating a table in the error report window,
        # which is created using the print_table() function from the pyRevit library.
        # The table is not created under certain conditions, and no errors occur.
        # For example, under the conditions - two identical lines of data, four
        # columns and in two adjacent cells of one line there are 17 characters
        # (numbers) and 52 characters (letters of the Russian alphabet).
        # The pyRevit and Markdown libraries were checked, but no solution was found.
        # It was found that adding an empty row to the end of the table solved
        # the problem, so let's implement it.

        # Была найдена проблема при создании таблицы в окне отчета об ошибках, которая создается
        # при помощи функции print_table() из библиотеки pyRevit. Таблица не создается при определенных условиях,
        # при этом не возникает никаких ошибок. Условия, при которых возникает проблема, связаны с количеством строк
        # и количеством символов в двух соседних ячейках одной строки. Например таблица не отображалась при 2 строках данных
        # и наличии в двух соседних ячейках текста количеством 17 символов (цифры) и 52 символа (буквы русского алфавита).
        # Проблема также наблюдается при написании текста английского алфавита при в 2 раза меньшем количестве символов.
        # Наблюдались и другие комбинации количество строк/символов, которые приводят к проблеме.
        # Поиск решения данной проблемы ни к чему не привел. Были проанализированы библиотеки pyRevit и Markdown.
        # В pyRevit функция print_table() преобразует передаваемый в нее список в строку в соответствии с системой разметки
        # Markdown и затем передает ее в функцию print_md() библиотеки pyRevit. В ней при помощи библиотеки Markdown строка преобразуется
        # в код HTML. При этом в функцию передается расширение, являющееся дополнительным конфигуратором данных для формирования
        # таблицы. Данное расширение создано на основе того, что представлено в стандартной библиотеке Markdown, но отчасти изменено.
        # Помимо этого в print_md() выполняеются дополнительные преобразования кода для корректности отображения в браузере
        # и в конце происходит печать print(html_code, end="").
        # На каждом этапе получаемая строка/html-код были проверены и ошибок найдено не было, исходя из этого пришли к выводу,
        # что проблема возникает в момент отображения html-кода во встроенном браузере окна от pyRevit.
        # Т.к. доступа для редактирования окна не имели приняли решения воспользоваться заглушкой в виде добавления в конец таблицы
        # дополнительной строки, содержащей в каждой ячейке "_", которая показала свою эффективность.

        missing_parameters.append(["_", "_", "_", "_"])
        return missing_parameters

    def __get_elements_sections(self, parameter_name):
        sections = {x.GetParamValue(parameter_name) for x in self.concrete}
        sections = sorted(sections)
        return [ElementSection(x) for x in sections]

    @reactive
    def concrete(self):
        return self.__concrete_by_table_type

    @reactive
    def rebar(self):
        return self.__rebar

    @reactive
    def buildings(self):
        return self.__buildings

    @reactive
    def construction_sections(self):
        return self.__construction_sections


class TableType:
    """
    This class used to represent a quality table type.
    """
    def __init__(self, name):
        self.__name = name
        self.__type_key_word = ""
        self.__categories = []
        self.__indexes_info = []

    @reactive
    def name(self):
        return self.__name

    @name.setter
    def name(self, value):
        self.__name = value

    @reactive
    def type_key_word(self):
        return self.__type_key_word

    @type_key_word.setter
    def type_key_word(self, value):
        self.__type_key_word = value

    @reactive
    def categories(self):
        return self.__categories

    @categories.setter
    def categories(self, value):
        self.__categories = value

    @reactive
    def indexes_info(self):
        return self.__indexes_info

    @indexes_info.setter
    def indexes_info(self, value):
        self.__indexes_info = value


class QualityIndex:
    """
    This class used to represent a line in a quality table type.
    """
    def __init__(self, name, number, index_type="", rebar_group=[]):
        self.__name = name
        self.__number = number
        self.__index_type = index_type
        self.__rebar_group = rebar_group

    @reactive
    def name(self):
        return self.__name

    @name.setter
    def name(self, value):
        self.__name = value

    @reactive
    def number(self):
        return self.__number

    @number.setter
    def number(self, value):
        self.__number = value

    @reactive
    def index_type(self):
        return self.__index_type

    @index_type.setter
    def index_type(self, value):
        self.__index_type = value

    @reactive
    def rebar_group(self):
        return self.__rebar_group

    @rebar_group.setter
    def rebar_group(self, value):
        self.__rebar_group = value


class ElementSection:
    """
    This class used to represent an object for grouping construction elements.
    For example building number or construction section.
    """
    def __init__(self, text_value):
        self.__text_value = text_value
        self.__number = text_value
        self.__is_checked = False

    @reactive
    def number(self):
        if self.__number:
            return self.__number
        else:
            return "<Параметр не заполнен>"

    @number.setter
    def number(self, value):
        self.__number = value

    @reactive
    def text_value(self):
        return self.__text_value

    @text_value.setter
    def text_value(self, value):
        self.__text_value = value

    @reactive
    def is_checked(self):
        return self.__is_checked

    @is_checked.setter
    def is_checked(self, value):
        self.__is_checked = value


class Construction:
    """
    This class created for all calculation of filtered construction elements.
    """
    def __init__(self, table_type, concrete_elements, rebar_elements):
        self.table_type = table_type
        self.concrete = concrete_elements
        self.rebar = rebar_elements

        self.__quality_indexes = dict()
        self.__rebar_by_function = dict()
        self.__rebar_mass_by_function = dict()

        self.__diameter_dict = {
            4: 0.098,
            5: 0.144,
            6: 0.222,
            7: 0.302,
            8: 0.395,
            9: 0.499,
            10: 0.617,
            12: 0.888,
            14: 1.208,
            16: 1.578,
            18: 1.998,
            20: 2.466,
            22: 2.984,
            25: 3.853,
            28: 4.834,
            32: 6.313,
            36: 7.990,
            40: 9.805
        }

        self.__intersection_dict = {
            8: 1.034,
            10: 1.043,
            12: 1.051,
            14: 1.060,
            16: 1.068,
            18: 1.077,
            20: 1.085,
            22: 1.094,
            25: 1.107,
            28: 1.120
        }

        self.__concrete_volume = 0
        self.__calculate_concrete_volume()

        self.__group_rebar_by_function()
        self.__calculate_rebar_group_mass()

        self.__set_building_info()
        self.__set_elements_sizes()
        self.__set_concrete_class()
        self.__set_concrete_volume()
        self.__set_rebar_indexes()

    def __calculate_rebar_element_mass(self, elements):
        rebar_mass = 0
        for element in elements:
            element_type = doc.GetElement(element.GetTypeId())
            is_ifc_element = element_type.GetParamValue(IFC_FAMILY)

            # diameter
            if element.IsExistsParam(REBAR_DIAMETER):
                diameter_param = element.GetParam(REBAR_DIAMETER)
            else:
                diameter_param = element_type.GetParam(REBAR_DIAMETER)
            diameter = convert_value(diameter_param)

            # mass per meter
            if element.IsExistsParam(FORM_NUMBER):
                form_number = element.GetParamValue(FORM_NUMBER)
            else:
                form_number = element_type.GetParamValue(FORM_NUMBER)

            if form_number < 200:
                if diameter in self.__diameter_dict.keys():
                    mass_per_metr = self.__diameter_dict[diameter]
                else:
                    mass_per_metr = 0
            else:
                if element.IsExistsParam(REBAR_MASS_PER_LENGTH):
                    mass_per_metr = element.GetParamValue(REBAR_MASS_PER_LENGTH)
                else:
                    mass_per_metr = element_type.GetParamValue(REBAR_MASS_PER_LENGTH)

            # length
            if hasattr(element, "DistributionType"):
                if element.DistributionType == DB.Structure.DistributionType.Uniform:
                    length_param = element.GetParam(REBAR_LENGTH)
                elif element.DistributionType == DB.Structure.DistributionType.VaryingLength:
                    length_param = element.GetParam(ROD_LENGTH)
            else:
                length_param = element.GetParam(REBAR_LENGTH)
            length = convert_value(length_param) * 0.001

            # type of calculation
            if element.IsExistsParam(REBAR_CALC_METERS):
                calculation_by_meters = element.GetParamValue(REBAR_CALC_METERS)
            else:
                calculation_by_meters = element_type.GetParamValue(REBAR_CALC_METERS)

            if calculation_by_meters:
                if length <= 11.7:
                    intersection_coef = 1
                elif hasattr(element, "DistributionType") and element.DistributionType == DB.Structure.DistributionType.VaryingLength:
                    intersection_coef = 1
                else:
                    if diameter in self.__intersection_dict.keys():
                        intersection_coef = self.__intersection_dict[diameter]
                    else:
                        intersection_coef = 1.1
                unit_mass = mass_per_metr * round(length * intersection_coef, 2)
            else:
                unit_mass = round(length * mass_per_metr, 2)

            if is_ifc_element:
                amount = element.GetParamValue(AMOUNT_SHARED_PARAM)
            else:
                amount = element.GetParamValue(AMOUNT)
                if hasattr(element, "DistributionType"):
                    if element.DistributionType == DB.Structure.DistributionType.VaryingLength:
                        amount = 1


            amount_on_level = element.GetParamValue(AMOUNT_ON_LEVEL)
            levels_amount = element.GetParamValue(AMOUNT_OF_LEVELS)

            element_mass = unit_mass * amount * amount_on_level * levels_amount
            rebar_mass += element_mass

        return rebar_mass

    def __calculate_rebar_group_mass(self):
        for key in self.__rebar_by_function.keys():
            elements = self.__rebar_by_function[key]
            rebar_mass = self.__calculate_rebar_element_mass(elements)
            self.__rebar_mass_by_function[key] = rebar_mass

    def __calculate_concrete_volume(self):
        for element in self.concrete:
            volume_param = element.GetParam(VOLUME)
            volume = convert_value(volume_param)
            self.__concrete_volume += volume

    def __group_rebar_by_function(self):
        for element in self.rebar:
            rebar_function = element.GetParamValue(CONSTR_GROUP)
            self.__rebar_by_function.setdefault(rebar_function, [])
            self.__rebar_by_function[rebar_function].append(element)

    def __set_building_info(self):
        project_info = doc.ProjectInformation
        value = project_info.GetParamValue(BUILDING_INFO)
        self.__quality_indexes["Этажность здания, тип секции"] = value

    def __set_elements_sizes(self):
        elements_sizes = set()
        walls_category = Category.GetCategory(doc, BuiltInCategory.OST_Walls)
        columns_category = Category.GetCategory(doc, BuiltInCategory.OST_StructuralColumns)
        floors_category = Category.GetCategory(doc, BuiltInCategory.OST_Floors)
        if self.table_type.name == "Пилоны":
            for element in self.concrete:
                element_type = doc.GetElement(element.GetTypeId())
                if element.Category.Id == columns_category.Id:
                    if element_type.IsExistsParam(HEIGHT_ADSK) and element_type.IsExistsParam(
                            WIDTH_ADSK):
                        height = element_type.GetParam(HEIGHT_ADSK).AsValueString()
                        width = element_type.GetParam(WIDTH_ADSK).AsValueString()
                        size = height + "х" + width
                        elements_sizes.add(size)
                if element.Category.Id == walls_category.Id:
                    if element_type.IsExistsParam(THICKNESS) and element.IsExistsParam(LENGTH):
                        height = element.GetParam(LENGTH).AsValueString()
                        width = element_type.GetParam(THICKNESS).AsValueString()
                        size = height + "х" + width
                        elements_sizes.add(size)
            elements_sizes = sorted(list(elements_sizes))
            self.__quality_indexes["Сечение пилонов, толщина х ширина, мм"] = ", ".join(elements_sizes)

            self.__quality_indexes[
                "Коэффициент суммарной площади сечений пилонов от площади перекрытия, ΣAw/Ap х 100"] = 0

        if self.table_type.name == "Стены":
            elements_sizes = self.__find_elements_width(self.concrete)
            self.__quality_indexes["Толщина стен, мм"] = ", ".join(elements_sizes)

        if self.table_type.name == "Фундаментная плита":
            elements_sizes = self.__find_elements_width(self.concrete)
            self.__quality_indexes["Толщина плиты, мм"] = ", ".join(elements_sizes)

        if self.table_type.name == "Плита перекрытия":
            floor_elements = [x for x in self.concrete if x.Category.Id == floors_category.Id]
            elements_sizes = self.__find_elements_width(floor_elements)
            self.__quality_indexes["Толщина плиты, мм"] = ", ".join(elements_sizes)

    def __find_elements_width(self, elements):
        elements_sizes = set()
        for element in elements:
            element_type = doc.GetElement(element.GetTypeId())
            if element_type.IsExistsParam(THICKNESS):
                width = element_type.GetParam(THICKNESS).AsValueString()
                elements_sizes.add(width)
        elements_sizes = sorted(list(elements_sizes))
        return elements_sizes

    def __set_concrete_class(self):
        concrete_classes = set()
        for element in self.concrete:
            element_type = doc.GetElement(element.GetTypeId())
            if element_type.IsExistsParam(CONCRETE_MARK):
                value = element_type.GetParam(CONCRETE_MARK).AsValueString()
                concrete_class = "В" + value
                concrete_classes.add(concrete_class)
        self.__quality_indexes["Класс бетона"] = ", ".join(concrete_classes)

    def __set_concrete_volume(self):
        self.__quality_indexes["Объем бетона, м3"] = self.__concrete_volume

    def __set_rebar_indexes(self):
        full_consumption = 0
        for index_info in self.table_type.indexes_info:
            if index_info.index_type == "mass" or index_info.index_type == "consumption":
                rebar_mass = 0
                rebar_function = index_info.rebar_group
                for function in rebar_function:
                    if function in self.__rebar_mass_by_function.keys():
                        rebar_mass += self.__rebar_mass_by_function[function]

                if index_info.index_type == "mass":
                    self.__quality_indexes[index_info.name] = rebar_mass
                elif index_info.index_type == "consumption":
                    consumption = rebar_mass / self.__concrete_volume
                    full_consumption += consumption
                    self.__quality_indexes[index_info.name] = consumption

        self.__quality_indexes["Общий расход, кг/м3"] = full_consumption

    @reactive
    def quality_indexes(self):
        return self.__quality_indexes


class QualityTable:
    """
    This class used to represent a quality table.
    This class has methods for creating schedule in revit and filling the schedule with data.
    """
    def __init__(self, table_type, construction, buildings, sections):
        self.table_type = table_type
        self.table_name = table_type.name
        buildings = [x.number for x in buildings]
        sections = [x.number for x in sections]
        buildings_str = "_".join(buildings).replace("<Параметр не заполнен>", "Без секции")
        sections_str = "_".join(sections).replace("<Параметр не заполнен>", "Без раздела")
        self.schedule_name = "РД_Показатели качества_" + table_type.name + "_" + buildings_str + "_" + sections_str
        self.indexes_info = table_type.indexes_info
        self.indexes_values = construction.quality_indexes

        self.table_width = 186
        self.table_width_column_1 = 10
        self.table_width_column_2 = 140
        self.table_width_column_3 = 35
        self.row_height = 8

    def create_table(self):
        schedule = self.find_schedule()
        if schedule:
            self.update_schedule_name(schedule)
        new_schedule = self.create_new_schedule(self.table_width)
        self.set_schedule_row_values(new_schedule)

    def find_schedule(self):
        schedules = FilteredElementCollector(doc).OfClass(ViewSchedule)
        fvp = ParameterValueProvider(ElementId(BuiltInParameter.VIEW_NAME))
        rule = FilterStringEquals()
        case_sens = False
        filter_rule = FilterStringRule(fvp, rule, self.schedule_name, case_sens)
        name_filter = ElementParameterFilter(filter_rule)
        schedules.WherePasses(name_filter)
        return schedules.FirstElement()

    def update_schedule_name(self, schedule):
        old_name = schedule.Name
        time = datetime.datetime.now().strftime("%Y-%m-%d %H.%M.%S")
        with revit.Transaction("BIM: Создание таблицы УПК"):
            schedule.Name = old_name + "_" + time

    def create_new_schedule(self, width):
        category_id = ElementId(BuiltInCategory.OST_Walls)
        with revit.Transaction("BIM: Создание таблицы УПК"):
            new_schedule = ViewSchedule.CreateSchedule(doc, category_id)
            new_schedule.Name = self.schedule_name

            s_definition = new_schedule.Definition
            s_definition.ShowHeaders = False
            table_data = new_schedule.GetTableData()
            header_data = table_data.GetSectionData(SectionType.Header)
            header_data.RemoveRow(0)

            field_type = ScheduleFieldType.Instance
            param_id = ElementId(BuiltInParameter.ALL_MODEL_INSTANCE_COMMENTS)
            s_field = s_definition.AddField(field_type, param_id)
            filter_value = "schedule_for_header"
            filter_rule = ScheduleFilterType.Equal
            my_filter = ScheduleFilter(s_field.FieldId, filter_rule, filter_value)
            s_definition.AddFilter(my_filter)

            s_field.SheetColumnWidth = convert_length(width)
        return new_schedule

    def options_cell_font(self, alignment=["left", "center", "right"]):
        tcs = TableCellStyle()
        options = TableCellStyleOverrideOptions()
        options.HorizontalAlignment = True
        options.Font = True
        options.FontSize = True
        tcs.FontName = "GOST Common"
        tcs.TextSize = 9.4482237
        tcs.SetCellStyleOverrideOptions(options)
        if alignment == "left":
            tcs.FontHorizontalAlignment = HorizontalAlignmentStyle.Left
        elif alignment == "central":
            tcs.FontHorizontalAlignment = HorizontalAlignmentStyle.Center
        elif alignment == "right":
            tcs.FontHorizontalAlignment = HorizontalAlignmentStyle.Right
        return tcs

    def set_schedule_row_values(self, schedule):
        table_data = schedule.GetTableData()
        header_data = table_data.GetSectionData(SectionType.Header)
        with revit.Transaction("BIM: Заполнение таблицы УПК"):
            header_data.InsertColumn(0)
            header_data.InsertColumn(1)
            header_data.SetColumnWidth(0, convert_length(self.table_width_column_1))
            header_data.SetColumnWidth(1, convert_length(self.table_width_column_2))
            header_data.SetColumnWidth(2, convert_length(self.table_width_column_3))

            header_data.InsertRow(0)
            height = 15
            header_data.SetRowHeight(0, convert_length(height))
            value1 = "№"
            header_data.SetCellStyle(0, 0, self.options_cell_font("central"))
            header_data.SetCellText(0, 0, value1)

            value2 = "Анализируемый параметр"
            header_data.SetCellStyle(0, 1, self.options_cell_font("central"))
            header_data.SetCellText(0, 1, value2)

            value3 = "Значения"
            header_data.SetCellStyle(0, 2, self.options_cell_font("central"))
            header_data.SetCellText(0, 2, value3)

            for i, quality_index in enumerate(self.indexes_info):
                header_data.InsertRow(i + 1)
                header_data.SetRowHeight(i + 1, convert_length(self.row_height))

                index_number = quality_index.number
                header_data.SetCellStyle(i + 1, 0, self.options_cell_font("central"))
                header_data.SetCellText(i + 1, 0, index_number)

                index_name = quality_index.name
                header_data.SetCellStyle(i + 1, 1, self.options_cell_font("left"))
                header_data.SetCellText(i + 1, 1, index_name)

                index_value = self.indexes_values[quality_index.name]
                if isinstance(index_value, float):
                    index_value = round(index_value, 2)
                index_value = str(index_value)
                header_data.SetCellStyle(i + 1, 2, self.options_cell_font("central"))
                header_data.SetCellText(i + 1, 2, index_value)


class CreateQualityTableCommand(ICommand):
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
        if not self.__view_model.buildings:
            self.__view_model.error_text = "ЖБ не найден в проекте"
            return False
        if not self.__view_model.revit_repository.rebar:
            self.__view_model.error_text = "Арматура не найдена в проекте"
            return False

        self.__view_model.error_text = None
        return True

    def Execute(self, parameter):
        buildings = self.__view_model.buildings
        construction_sections = self.__view_model.construction_sections
        selected_blds = [x for x in buildings if x.is_checked]
        selected_sctns = [x for x in construction_sections if x.is_checked]
        concrete = self.__view_model.revit_repository.get_filtered_concrete_by_user(selected_blds, selected_sctns)
        rebar = self.__view_model.revit_repository.get_filtered_rebar_by_blds_and_scts(selected_blds, selected_sctns)
        check = self.__view_model.revit_repository.check_filtered_rebar(rebar)
        if check:
            output = script.get_output()
            output.print_table(table_data=check,
                               title="Показатели качества",
                               columns=["Категории", "Тип ошибки", "Название параметра", "Id"])
            script.exit()
        rebar = self.__view_model.revit_repository.get_filtered_rebar_by_table_type(rebar)

        if not concrete:
            alert("Не найден ЖБ для выбранных секций и разделов")
        elif not rebar:
            alert("Не найдена арматура для выбранных секций и разделов")
        else:
            selected_table_type = self.__view_model.selected_table_type
            construction = Construction(selected_table_type, concrete, rebar)
            quality_table = QualityTable(selected_table_type, construction, selected_blds, selected_sctns)
            quality_table.create_table()
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
    def __init__(self, revit_repository, table_types):
        Reactive.__init__(self)
        self.__table_types = table_types
        self.__revit_repository = revit_repository
        self.__buildings = []
        self.__construction_sections = []
        self.__error_text = ""

        self.__create_tables_command = CreateQualityTableCommand(self)

        self.selected_table_type = table_types[0]

    @reactive
    def revit_repository(self):
        return self.__revit_repository

    @reactive
    def table_types(self):
        return self.__table_types

    @reactive
    def selected_table_type(self):
        return self.__selected_table_type

    @selected_table_type.setter
    def selected_table_type(self, value):
        self.revit_repository.set_table_type(value)
        self.buildings = self.__revit_repository.buildings
        self.construction_sections = self.__revit_repository.construction_sections
        self.__selected_table_type = value

    @reactive
    def buildings(self):
        return self.__buildings

    @buildings.setter
    def buildings(self, value):
        self.__buildings = value

    @reactive
    def construction_sections(self):
        return self.__construction_sections

    @construction_sections.setter
    def construction_sections(self, value):
        self.__construction_sections = value

    @reactive
    def error_text(self):
        return self.__error_text

    @error_text.setter
    def error_text(self, value):
        self.__error_text = value

    @property
    def create_tables_command(self):
        return self.__create_tables_command


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
    table_types = []

    walls_cat = Category.GetCategory(doc, BuiltInCategory.OST_Walls)
    columns_cat = Category.GetCategory(doc, BuiltInCategory.OST_StructuralColumns)
    foundation_cat = Category.GetCategory(doc, BuiltInCategory.OST_StructuralFoundation)
    floor_cat = Category.GetCategory(doc, BuiltInCategory.OST_Floors)
    framing_cat = Category.GetCategory(doc, BuiltInCategory.OST_StructuralFraming)

    walls_table_type = TableType("Стены")
    walls_table_type.categories = [walls_cat]
    walls_table_type.type_key_word = ["Стена"]
    walls_table_type.indexes_info = [
        QualityIndex("Этажность здания, тип секции", "1"),
        QualityIndex("Толщина стен, мм", "2"),
        QualityIndex("Класс бетона", "3"),
        QualityIndex("Объем бетона, м3", "4"),
        QualityIndex("Масса вертикальной арматуры, кг", "5.1", "mass", ["Стена_Вертикальная"]),
        QualityIndex("Расход вертикальной арматуры, кг/м3", "5.2", "consumption", ["Стена_Вертикальная"]),
        QualityIndex("Масса горизонтальной арматуры, кг", "6.1", "mass", ["Стена_Горизонтальная"]),
        QualityIndex("Расход горизонтальной арматуры, кг/м3", "6.2", "consumption", ["Стена_Горизонтальная"]),
        QualityIndex("Масса конструктивной арматуры, кг", "7.1", "mass", ["Стена_Конструктивная"]),
        QualityIndex("Расход конструктивной арматуры, кг/м3", "7.2", "consumption", ["Стена_Конструктивная"]),
        QualityIndex("Общий расход, кг/м3", "8")]

    columns_table_type = TableType("Пилоны")
    columns_table_type.categories = [walls_cat, columns_cat]
    columns_table_type.type_key_word = ["Пилон"]
    columns_table_type.indexes_info = [
        QualityIndex("Этажность здания, тип секции", "1"),
        QualityIndex("Сечение пилонов, толщина х ширина, мм", "2"),
        QualityIndex("Класс бетона", "3"),
        QualityIndex("Объем бетона, м3", "4"),
        QualityIndex("Коэффициент суммарной площади сечений пилонов от площади перекрытия, ΣAw/Ap х 100", "5"),
        QualityIndex("Масса продольной арматуры, кг", "6.1", "mass", ["Пилон_Продольная"]),
        QualityIndex("Расход продольной арматуры, кг/м3", "6.2", "consumption", ["Пилон_Продольная"]),
        QualityIndex("Масса поперечной арматуры, кг", "7.1", "mass", ["Пилон_Поперечная"]),
        QualityIndex("Расход поперечной арматуры, кг/м3", "7.2", "consumption", ["Пилон_Поперечная"]),
        QualityIndex("Общий расход, кг/м3", "8")]

    foundation_table_type = TableType("Фундаментная плита")
    foundation_table_type.categories = [floor_cat, foundation_cat, walls_cat]
    foundation_table_type.type_key_word = ["ФПлита"]
    foundation_table_type.indexes_info = [
        QualityIndex("Этажность здания, тип секции", "1"),
        QualityIndex("Толщина плиты, мм", "2"),
        QualityIndex("Класс бетона", "3"),
        QualityIndex("Объем бетона, м3", "4"),
        QualityIndex("Масса нижней фоновой арматуры, кг", "5.1", "mass", ["ФП_Фон_Н", "ФП_Фон_Низ"]),
        QualityIndex("Расход нижней фоновой арматуры, кг/м3", "5.2", "consumption", ["ФП_Фон_Н", "ФП_Фон_Низ"]),
        QualityIndex("Масса нижней арматуры усиления, кг", "5.3", "mass", ["ФП_Усиление_Н", "ФП_Доп_Н", "ФП_Доп_Низ"]),
        QualityIndex("Расход нижней арматуры усиления, кг/м3", "5.4", "consumption", ["ФП_Усиление_Н", "ФП_Доп_Н", "ФП_Доп_Низ"]),
        QualityIndex("Масса верхней фоновой арматуры, кг", "6.1", "mass", ["ФП_Фон_В", "ФП_Фон_Верх"]),
        QualityIndex("Расход верхней фоновой арматуры, кг/м3", "6.2", "consumption", ["ФП_Фон_В", "ФП_Фон_Верх"]),
        QualityIndex("Масса верхней арматуры усиления, кг", "6.3", "mass", ["ФП_Усиление_В", "ФП_Доп_В", "ФП_Доп_Верх"]),
        QualityIndex("Расход верхней арматуры усиления, кг/м3", "6.4", "consumption", ["ФП_Усиление_В", "ФП_Доп_В", "ФП_Доп_Верх"]),
        QualityIndex("Масса поперечной арматуры в зонах продавливания, кг", "7.1", "mass", ["ФП_Каркасы_Продавливание", "ФП_Поперечная"]),
        QualityIndex("Расход поперечной арматуры в зонах продавливания, кг/м3", "7.2", "consumption", ["ФП_Каркасы_Продавливание", "ФП_Поперечная"]),
        QualityIndex("Масса конструктивной арматуры, кг", "7.3", "mass", ["ФП_Конструктивная", "ФП_Каркасы_Поддерживающие"]),
        QualityIndex("Расход конструктивной арматуры, кг/м3", "7.4", "consumption", ["ФП_Конструктивная", "ФП_Каркасы_Поддерживающие"]),
        QualityIndex("Масса выпусков, кг", "8.1", "mass", ["ФП_Выпуски"]),
        QualityIndex("Расход выпусков, кг/м3", "8.2", "consumption", ["ФП_Выпуски"]),
        QualityIndex("Масса закладных, кг", "9.1", "mass", ["ФП_Закладная"]),
        QualityIndex("Расход закладных, кг/м3", "9.2", "consumption", ["ФП_Закладная"]),
        QualityIndex("Общий расход, кг/м3", "10")]

    floor_table_type = TableType("Плита перекрытия")
    floor_table_type.categories = [floor_cat, framing_cat, walls_cat]
    floor_table_type.type_key_word = ["Перекрытие", "Балка"]
    floor_table_type.indexes_info = [
        QualityIndex("Этажность здания, тип секции", "1"),
        QualityIndex("Толщина плиты, мм", "2"),
        QualityIndex("Класс бетона", "3"),
        QualityIndex("Объем бетона, м3", "4"),
        QualityIndex("Масса нижней фоновой арматуры, кг", "5.1", "mass", ["ПП_Фон_Н", "ПП_Фон_Низ"]),
        QualityIndex("Расход нижней фоновой арматуры, кг/м3", "5.2", "consumption", ["ПП_Фон_Н", "ПП_Фон_Низ"]),
        QualityIndex("Масса нижней арматуры усиления, кг", "5.3", "mass", ["ПП_Усиление_Н", "ПП_Доп_Н", "ПП_Доп_Низ"]),
        QualityIndex("Расход нижней арматуры усиления, кг/м3", "5.4", "consumption", ["ПП_Усиление_Н", "ПП_Доп_Н", "ПП_Доп_Низ"]),
        QualityIndex("Масса верхней фоновой арматуры, кг", "6.1", "mass", ["ПП_Фон_В", "ПП_Фон_Верх"]),
        QualityIndex("Расход верхней фоновой арматуры, кг/м3", "6.2", "consumption", ["ПП_Фон_В", "ПП_Фон_Верх"]),
        QualityIndex("Масса верхней арматуры усиления, кг", "6.3", "mass", ["ПП_Усиление_В", "ПП_Доп_В", "ПП_Доп_Верх"]),
        QualityIndex("Расход верхней арматуры усиления, кг/м3", "6.4", "consumption", ["ПП_Усиление_В", "ПП_Доп_В", "ПП_Доп_Верх"]),
        QualityIndex("Масса поперечной арматуры в зонах продавливания, кг", "7.1", "mass", ["ПП_Каркасы_Продавливание", "ПП_Поперечная"]),
        QualityIndex("Расход поперечной арматуры в зонах продавливания, кг/м3", "7.2", "consumption", ["ПП_Каркасы_Продавливание", "ПП_Поперечная"]),
        QualityIndex("Масса конструктивной арматуры, кг", "8.1", "mass", ["ПП_Конструктивная", "ПП_Каркасы_Поддерживающие"]),
        QualityIndex("Расход конструктивной арматуры, кг/м3", "8.2", "consumption", ["ПП_Конструктивная", "ПП_Каркасы_Поддерживающие"]),
        QualityIndex("Масса арматуры балок, кг", "9.1", "mass", ["ПП_Балки"]),
        QualityIndex("Расход арматуры балок, кг/м3", "9.2", "consumption", ["ПП_Балки"]),
        QualityIndex("Общий расход, кг/м3", "10")]

    table_types.append(walls_table_type)
    table_types.append(columns_table_type)
    table_types.append(foundation_table_type)
    table_types.append(floor_table_type)

    revit_repository = RevitRepository(doc)
    check = revit_repository.check_exist_main_parameters()
    if check:
        # Данный код оставлен для быстрого тестирования неизвестной ошибки, описанной в функции __create_error_list()
        # for error in check:
        #     print("Категория ошибки: " + error[0])
        #     print("Описание ошибки: " + error[1])
        #     print("Название параметра: " + error[2])
        #     print("ID элементов: " + error[3])
        #
        #     print("----------------------------------")
        output = script.get_output()
        output.print_table(table_data=check,
                           title="Показатели качества",
                           columns=["Категории", "Тип ошибки", "Название параметра", "Id"])
        script.exit()

    revit_repository.filter_by_main_parameters()

    check = revit_repository.check_exist_rebar_parameters()
    if check:
        # for error in check:
        #     print("Категория ошибки: " + error[0])
        #     print("Описание ошибки: " + error[1])
        #     print("Название параметра: " + error[2])
        #     print("ID элементов: " + error[3])
        #
        #     print("----------------------------------")
        output = script.get_output()
        output.print_table(table_data=check,
                           title="Показатели качества",
                           columns=["Категории", "Тип ошибки", "Название параметра", "Id"])
        script.exit()

    check = revit_repository.check_parameters_values()
    if check:
        # for error in check:
        #     print("Категория ошибки: " + error[0])
        #     print("Описание ошибки: " + error[1])
        #     print("Название параметра: " + error[2])
        #     print("ID элементов: " + error[3])
        #
        #     print("----------------------------------")
        output = script.get_output()
        output.print_table(table_data=check,
                           title="Показатели качества",
                           columns=["Категории", "Тип ошибки", "Название параметра", "Id"])
        script.exit()

    main_window = MainWindow()
    main_window.DataContext = MainWindowViewModel(revit_repository, table_types)
    main_window.show_dialog()
    if not main_window.DialogResult:
        script.exit()


script_execute()
