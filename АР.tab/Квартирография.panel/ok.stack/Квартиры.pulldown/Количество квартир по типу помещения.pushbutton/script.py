# -*- coding: utf-8 -*-
import os.path as op
import os
import sys
import collections

from Autodesk.Revit.DB import FilteredElementCollector, BuiltInCategory
__doc__ = 'Определяет тип и количество Помещений\Квартир.'

def GroupByParameter(lst, func):
    res = {}
    for el in lst:
        key = func(el)
        if key in res:
            res[key].append(el)
        else:
            res[key] = [el]
    return res

doc = __revit__.ActiveUIDocument.Document
uidoc = __revit__.ActiveUIDocument


collector = {}
collectorBySection = {}
rooms = FilteredElementCollector(doc).OfCategory(BuiltInCategory.OST_Rooms).ToElements()
rooms = GroupByParameter(rooms, func = lambda x: x.LookupParameter('Уровень').AsValueString())

for level in rooms:
    rooms[level] = GroupByParameter(rooms[level], func = lambda x: x.LookupParameter('КГ_Корпус.Секция').AsValueString())
    for section in rooms[level]:
        bySection = {}
        if section in collectorBySection:
            bySection = collectorBySection[section]
        else:
            bySection = {}

        rooms[level][section] = GroupByParameter(rooms[level][section], func = lambda x: x.LookupParameter('КГ_Имя подгруппы помещений').AsValueString())
        for flat in rooms[level][section]:
            name = rooms[level][section][flat][0].LookupParameter('КГ_Тип помещения').AsValueString()
            if name in collector:
                collector[name] += 1
            else:
                collector[name] = 1

            if name in bySection:
                bySection[name] +=1
            else:
                bySection[name] = 1

        collectorBySection[section] = bySection

            
print '|{:-^40}|'.format('')
print '|{:-^40}|'.format('Количество квартир по проекту')
print '|{:-^40}|'.format('')
for key in collections.OrderedDict(sorted(collector.items())):
    print '|'+key + ': ' + str(collector[key])
print '|{:/^40}|'.format('')
print '|{:/^40}|'.format('')
print '|'
for section in collections.OrderedDict(sorted(collectorBySection.items())):
    d = collectorBySection[section]
    print '|{:-^40}|'.format('')
    print '|{:-^40}|'.format('Количество квартир в ' + section)
    print '|{:-^40}|'.format('')
    for key in collections.OrderedDict(sorted(d.items())):
        print '|'+key + ': ' + str(d[key])