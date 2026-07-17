import argparse
import os
import glob
import time
import xlrd
import csv
import prettytable as pt
import numpy as np
from lxml import etree
import math
from openpyxl import load_workbook
import pandas as pd
import brickschema
from brickschema.namespaces import A, BRICK, UNIT
from rdflib import Graph, Literal, RDF, URIRef, RDFS, Namespace
import math
import ast
import xml.etree.ElementTree as ET
from rdflib.plugins.sparql import prepareQuery

BLDG = Namespace("urn:OPS#")


def bridge_VAV(g_informative_topology):
    # Extract the air terminal, which link with one air supply source
    air_source_list = []
    for s, p, o in g_informative_topology.triples((None, BRICK.feedsAir, None)):
        if (o, A, BRICK.Air_Diffuser) in g_informative_topology:
            air_source_list.append(s.fragment)
    air_source_list = list(set(air_source_list))  # VAV, AHU, MVHR, FCU

    source2terminal_dict = {str(air_source): [] for air_source in air_source_list}
    for s_1, p_1, o_1 in g_informative_topology.triples((None, A, BRICK.Air_Diffuser)):
        for s_2, p_2, o_2 in g_informative_topology.triples((None, BRICK.feedsAir, s_1)):
            source2terminal_dict[s_2.fragment].append(s_1.fragment)

    # Extract the VAV2terminal
    VAV2terminal_dict = {attribute: value for attribute, value in source2terminal_dict.items() if "-VAV-" in attribute}
    VAV2room_dict = {str(VAV): [] for VAV in list(VAV2terminal_dict.keys())}

    for VAV in list(VAV2room_dict.keys()):
        for terminal in VAV2terminal_dict[VAV]:
            for s, p, o in g_informative_topology.triples((BLDG[terminal], BRICK.feedsAir, None)):
                VAV2room_dict[VAV].append(o.fragment)
    for key, lst in VAV2room_dict.items():
        unique_list = list(set(lst))
        VAV2room_dict[key] = unique_list

    room2multiterminals = [key for key, value in VAV2room_dict.items() if len(value) > 1]
    if not room2multiterminals:
        print("No room having more than one VAV boxes!")
    else:
        print("Room have more than one VAV boxes!")
        print(room2multiterminals)

    # Create the BRICK.feedsAir from VAV to room and delete the relevant air terminals
    for VAV in list(VAV2room_dict.keys()):
        g_informative_topology.add((BLDG[VAV], BRICK.feedsAir, BLDG[VAV2room_dict[VAV][0]]))
        for terminal in list(VAV2terminal_dict[VAV]):
            g_informative_topology.remove((BLDG[terminal], None, None))
            g_informative_topology.remove((None, None, BLDG[terminal]))

    return g_informative_topology

def merge_RAD(g_informative_topology):
    # merge radiators. Includes the generic BRICK.Space_Heater class alongside
    # BRICK.Radiator: IFC-to-Brick's mapping tables only tag an IfcSpaceHeater
    # as the specific "Radiator" subclass when its PredefinedType is set to
    # RADIATOR - real-world exports frequently leave PredefinedType unset/
    # NOTDEFINED, in which case the generic "Space_Heater" entry applies
    # instead (confirmed on the real b03 heating test data: all 7 real
    # radiators came through as Space_Heater, not Radiator) - restricting
    # this to only BRICK.Radiator silently merges nothing on such data.
    room_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.Room)):
        room_list.append(s.fragment)
    room_list = list(set(room_list))

    RAD_type_list = [BRICK.Radiator, BRICK.Space_Heater]
    for RAD_type in RAD_type_list:
        RAD_list = []
        for s, p, o in g_informative_topology.triples((None, A, RAD_type)):
            RAD_list.append(s.fragment)
        RAD_list = list(set(RAD_list))

        room2RAD_dict = {str(room): [] for room in room_list}
        for room in room_list:
            for RAD in g_informative_topology.subjects(A, RAD_type):
                if (RAD, BRICK.hasLocation, BLDG[room]) in g_informative_topology:
                    room2RAD_dict[str(room)].append(RAD.fragment)

        RAD2pump_dict = {str(RAD): [] for RAD in RAD_list}
        for RAD in RAD_list:
            for s_1, p_1, o_1 in g_informative_topology.triples((None, BRICK.feeds, BLDG[RAD])):
                RAD2pump_dict[RAD].append(s_1.fragment)

        # Create the BRICK.feeds from RAD to room and delete the relevant RADs
        for room in list(room2RAD_dict.keys()):
            if len(room2RAD_dict[room]) != 0:  # have radiators
                VRAD_id = room + "-V-RAD"
                g_informative_topology.add((BLDG[VRAD_id], A, BRICK.Radiator))  # Create virtual RAD
                g_informative_topology.add((BLDG[VRAD_id], BRICK.feeds, BLDG[room]))  # Create BRICK.feedss
                for RAD in list(room2RAD_dict[room]):
                    for pump in list(RAD2pump_dict[RAD]):
                        g_informative_topology.add((BLDG[pump], BRICK.feeds, BLDG[VRAD_id]))
                    g_informative_topology.remove((BLDG[RAD], None, None))
                    g_informative_topology.remove((None, None, BLDG[RAD]))

    return g_informative_topology

def merge_FCU(g_informative_topology):
    room_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.Room)):
        room_list.append(s.fragment)
    room_list = list(set(room_list))

    # Merge FCUs
    FCU_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.FCU)):
        FCU_list.append(s.fragment)
    FCU_list = list(set(FCU_list))

    room2FCU_dict = {str(room): [] for room in room_list}
    for room in room_list:
        for FCU in g_informative_topology.subjects(A, BRICK.FCU):
            if (FCU, BRICK.feedsAir, BLDG[room]) in g_informative_topology:
                room2FCU_dict[str(room)].append(FCU.fragment)

    FCU2pump_dict = {str(FCU): [] for FCU in FCU_list}
    FCU2MVHR_dict = {str(FCU): [] for FCU in FCU_list}
    for FCU in FCU_list:
        for s, p, o in g_informative_topology.triples((None, BRICK.feeds, BLDG[FCU])):
            FCU2pump_dict[FCU].append(s.fragment)
        for s, p, o in g_informative_topology.triples((None, BRICK.feedsAir, BLDG[FCU])):
            FCU2MVHR_dict[FCU].append(s.fragment)

    # Create the BRICK.feeds from FCU to room and delete the relevant FCUs
    for room in list(room2FCU_dict.keys()):
        if len(room2FCU_dict[room]) != 0:  # have FCUs
            VFCU_id = room + "-V-FCU"
            g_informative_topology.add((BLDG[VFCU_id], A, BRICK.FCU))  # Create virtual FCU
            g_informative_topology.add((BLDG[VFCU_id], BRICK.feedsAir, BLDG[room]))  # Create BRICK.feedss
            for FCU in list(room2FCU_dict[room]):
                for pump in list(FCU2pump_dict[FCU]):
                    g_informative_topology.add((BLDG[pump], BRICK.feeds, BLDG[VFCU_id]))
                for MVHR in list(FCU2MVHR_dict[FCU]):
                    g_informative_topology.add((BLDG[MVHR], BRICK.feedsAir, BLDG[VFCU_id]))
                g_informative_topology.remove((BLDG[FCU], None, None))
                g_informative_topology.remove((None, None, BLDG[FCU]))

    return g_informative_topology

def merge_VAV(g_informative_topology):
    room_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.Room)):
        room_list.append(s.fragment)
    room_list = list(set(room_list))

    # Merge VAVs
    VAV_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.VAV)):
        VAV_list.append(s.fragment)
    VAV_list = list(set(VAV_list))

    room2VAV_dict = {str(room): [] for room in room_list}
    for room in room_list:
        for VAV in g_informative_topology.subjects(A, BRICK.VAV):
            if (VAV, BRICK.feedsAir, BLDG[room]) in g_informative_topology:
                room2VAV_dict[str(room)].append(VAV.fragment)

    VAV2AHU_dict = {str(VAV): [] for VAV in VAV_list}
    for s_1, p_1, o_1 in g_informative_topology.triples((None, A, BRICK.VAV)):
        for s_2, p_2, o_2 in g_informative_topology.triples((None, BRICK.feedsAir, s_1)):
            VAV2AHU_dict[s_1.fragment].append(s_2.fragment)

    # Create the BRICK.feedsAir from VAV to room and delete the relevant VAVs
    for room in list(room2VAV_dict.keys()):
        if len(room2VAV_dict[room]) != 0:  # have FCUs
            VVAV_id = room + "-V-VAV"
            g_informative_topology.add((BLDG[VVAV_id], A, BRICK.VAV))  # Create virtual RAD
            g_informative_topology.add((BLDG[VVAV_id], BRICK.feedsAir, BLDG[room]))  # Create BRICK.feedss
            for VAV in list(room2VAV_dict[room]):
                for AHU in list(VAV2AHU_dict[VAV]):
                    g_informative_topology.add((BLDG[AHU], BRICK.feedsAir, BLDG[VVAV_id]))
                g_informative_topology.remove((BLDG[VAV], None, None))
                g_informative_topology.remove((None, None, BLDG[VAV]))

    return g_informative_topology


def merge_CAV(g_informative_topology):
    room_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.Room)):
        room_list.append(s.fragment)
    room_list = list(set(room_list))

    # Merge VAVs
    CAV_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.Air_Diffuser)):
        for source, _, _ in g_informative_topology.triples((None, BRICK.feedsAir, s)):
            if not (source, A, BRICK.VAV) in g_informative_topology:
                CAV_list.append(s.fragment)
    CAV_list = list(set(CAV_list))

    room2CAV_dict = {str(room): [] for room in room_list}
    for room in room_list:
        for CAV in g_informative_topology.subjects(A, BRICK.Air_Diffuser):
            if (CAV, BRICK.feedsAir, BLDG[room]) in g_informative_topology:
                for source, _, _ in g_informative_topology.triples((None, BRICK.feedsAir, CAV)):
                    if not (source, A, BRICK.VAV) in g_informative_topology:
                        room2CAV_dict[str(room)].append(CAV.fragment)

    CAV2AHU_dict = {str(CAV): [] for CAV in CAV_list}
    for s_1, p_1, o_1 in g_informative_topology.triples((None, A, BRICK.Air_Diffuser)):
        for s_2, p_2, o_2 in g_informative_topology.triples((None, BRICK.feedsAir, s_1)):
            CAV2AHU_dict[s_1.fragment].append(s_2.fragment)

    # Create the BRICK.feedsAir from CAV to room and delete the relevant CAVs
    for room in list(room2CAV_dict.keys()):
        if len(room2CAV_dict[room]) != 0:  # have FCUs
            VCAV_id = room + "-V-CAV"
            g_informative_topology.add((BLDG[VCAV_id], A, BRICK.CAV))  # Create virtual RAD
            g_informative_topology.add((BLDG[VCAV_id], BRICK.feedsAir, BLDG[room]))  # Create BRICK.feedss
            for CAV in list(room2CAV_dict[room]):
                for AHU in list(CAV2AHU_dict[CAV]):
                    g_informative_topology.add((BLDG[AHU], BRICK.feedsAir, BLDG[VCAV_id]))
                g_informative_topology.remove((BLDG[CAV], None, None))
                g_informative_topology.remove((None, None, BLDG[CAV]))

    return g_informative_topology

def merge_Pump(g_informative_topology):
    # merge HW/CW pumps. Includes the generic BRICK.Pump class alongside the
    # CW/HW-specific ones: IFC-to-Brick's mapping tables classify most real
    # pumps as generic "Pump" (no CW/HW split available from IFC type alone),
    # so restricting this to only the two specific subtypes silently merges
    # nothing on real-world data.
    Pump_type_list = [BRICK.Chilled_Water_Pump, BRICK.Hot_Water_Pump, BRICK.Pump]
    for Pump_type in Pump_type_list:
        Pump_list = []
        for s, p, o in g_informative_topology.triples((None, A, Pump_type)):
            Pump_list.append(s.fragment)
        Pump_list = list(set(Pump_list))

        Pump2Link_dict = {str(Pump): [] for Pump in Pump_list}
        for Pump in Pump_list:
            for s, p, o in g_informative_topology.triples((BLDG[Pump], BRICK.feeds, None)):
                Pump2Link_dict[s.fragment].append(o.fragment)
            for s, p, o in g_informative_topology.triples((None, BRICK.feeds, BLDG[Pump])):
                Pump2Link_dict[o.fragment].append(s.fragment)

        Pump_group_list = find_keys_with_identical_lists(Pump2Link_dict)

        PumpGroup_num = 0
        for Pump_group in list(Pump_group_list):
            PumpGroup_num += 1
            PumpGroup_id = Pump_type.fragment + "-Group-" + str(PumpGroup_num)
            g_informative_topology.add((BLDG[PumpGroup_id], A, Pump_type))
            Pump_group = list(Pump_group)
            for Pump in Pump_group:
                for s, p, o in g_informative_topology.triples((BLDG[Pump], BRICK.feeds, None)):
                    g_informative_topology.add((BLDG[PumpGroup_id], BRICK.feeds, o))
                for s, p, o in g_informative_topology.triples((None, BRICK.feeds, BLDG[Pump])):
                    g_informative_topology.add((s, BRICK.feeds, BLDG[PumpGroup_id]))
                g_informative_topology.remove((BLDG[Pump], None, None))
                g_informative_topology.remove((None, None, BLDG[Pump]))

    return g_informative_topology


def merge_DH(g_informative_topology):
    room_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.Room)):
        room_list.append(s.fragment)
    room_list = list(set(room_list))

    # Merge Radiators
    DH_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.DH)):
        DH_list.append(s.fragment)
    DH_list = list(set(DH_list))

    room2DH_dict = {str(room): [] for room in room_list}
    for room in room_list:
        for DH in g_informative_topology.subjects(A, BRICK.DH):
            if (DH, BRICK.feedsAir, BLDG[room]) in g_informative_topology:
                room2DH_dict[str(room)].append(DH.fragment)

    DH2pump_dict = {str(DH): [] for DH in DH_list}
    for DH in DH_list:
        for s_1, p_1, o_1 in g_informative_topology.triples((None, BRICK.feeds, BLDG[DH])):
            DH2pump_dict[DH].append(s_1.fragment)

    # Create the BRICK.feeds from DH to room and delete the relevant DHs
    for room in list(room2DH_dict.keys()):
        if len(room2DH_dict[room]) != 0:  # have DHs
            VDH_id = room + "-V-DH"
            g_informative_topology.add((BLDG[VDH_id], A, BRICK.DH))  # Create virtual RAD
            g_informative_topology.add((BLDG[VDH_id], BRICK.feedsAir, BLDG[room]))  # Create BRICK.feeds
            for DH in list(room2DH_dict[room]):
                for pump in list(DH2pump_dict[DH]):
                    g_informative_topology.add((BLDG[pump], BRICK.feeds, BLDG[VDH_id]))
                g_informative_topology.remove((BLDG[DH], None, None))
                g_informative_topology.remove((None, None, BLDG[DH]))

    return g_informative_topology

def merge_AC(g_informative_topology):
    room_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.Room)):
        room_list.append(s.fragment)
    room_list = list(set(room_list))

    # Merge Radiators
    AC_list = []
    for s, p, o in g_informative_topology.triples((None, A, BRICK.AC)):
        AC_list.append(s.fragment)
    AC_list = list(set(AC_list))

    room2AC_dict = {str(room): [] for room in room_list}
    for room in room_list:
        for AC in g_informative_topology.subjects(A, BRICK.AC):
            if (AC, BRICK.feedsAir, BLDG[room]) in g_informative_topology:
                room2AC_dict[str(room)].append(AC.fragment)

    AC2pump_dict = {str(AC): [] for AC in AC_list}
    for AC in AC_list:
        for s_1, p_1, o_1 in g_informative_topology.triples((None, BRICK.feeds, BLDG[AC])):
            AC2pump_dict[AC].append(s_1.fragment)

    # Create the BRICK.feeds from AC to room and delete the relevant ACs
    for room in list(room2AC_dict.keys()):
        if len(room2AC_dict[room]) != 0:  # have ACs
            VAC_id = room + "-V-AC"
            g_informative_topology.add((BLDG[VAC_id], A, BRICK.AC))  # Create virtual RAD
            g_informative_topology.add((BLDG[VAC_id], BRICK.feedsAir, BLDG[room]))  # Create BRICK.feeds
            for AC in list(room2AC_dict[room]):
                for pump in list(AC2pump_dict[AC]):
                    g_informative_topology.add((BLDG[pump], BRICK.feeds, BLDG[VAC_id]))
                g_informative_topology.remove((BLDG[AC], None, None))
                g_informative_topology.remove((None, None, BLDG[AC]))

    return g_informative_topology


def merge_HX(g_informative_topology):
    # merge HX. Includes BRICK.Heat_Exchanger alongside BRICK.HX: IFC-to-Brick's
    # mapping tables classify IfcHeatExchanger as "Heat_Exchanger", not "HX" -
    # restricting this to only "HX" silently merges nothing on real-world data.
    HX_type_list = [BRICK.HX, BRICK.Heat_Exchanger]
    for HX_type in HX_type_list:
        HX_list = []
        for s, p, o in g_informative_topology.triples((None, A, HX_type)):
            HX_list.append(s.fragment)
        HX_list = list(set(HX_list))

        HX2Link_dict = {str(HX): [] for HX in HX_list}
        for HX in HX_list:
            for s, p, o in g_informative_topology.triples((BLDG[HX], BRICK.feeds, None)):
                HX2Link_dict[s.fragment].append(o.fragment)
            for s, p, o in g_informative_topology.triples((None, BRICK.feeds, BLDG[HX])):
                HX2Link_dict[o.fragment].append(s.fragment)

        HX_group_list = find_keys_with_identical_lists(HX2Link_dict)

        HXGroup_num = 0
        for HX_group in list(HX_group_list):
            HXGroup_num += 1
            HXGroup_id = HX_type.fragment + "-Group-" + str(HXGroup_num)
            g_informative_topology.add((BLDG[HXGroup_id], A, HX_type))
            HX_group = list(HX_group)
            for HX in HX_group:
                for s, p, o in g_informative_topology.triples((BLDG[HX], BRICK.feeds, None)):
                    g_informative_topology.add((BLDG[HXGroup_id], BRICK.feeds, o))
                for s, p, o in g_informative_topology.triples((None, BRICK.feeds, BLDG[HX])):
                    g_informative_topology.add((s, BRICK.feeds, BLDG[HXGroup_id]))
                g_informative_topology.remove((BLDG[HX], None, None))
                g_informative_topology.remove((None, None, BLDG[HX]))

    return g_informative_topology

def find_keys_with_identical_lists(d):
    from collections import defaultdict
    temp_dict = defaultdict(list)
    for key, value in d.items():
        sorted_tuple = tuple(sorted(value))
        temp_dict[sorted_tuple].append(key)
    return {tuple(value) for value in temp_dict.values()}


def merge_dictionaries(dict1, dict2):
    # 创建一个新的字典来存储合并后的结果
    merged_dict = {}
    # 先将第一个字典的内容复制到merged_dict中
    for key, value in dict1.items():
        merged_dict[key] = value
    # 遍历第二个字典，添加或合并内容
    for key, value in dict2.items():
        if key in merged_dict:
            # 如果key已经存在，将内容拼接起来
            # 这里假设字典的值是列表
            merged_dict[key].extend(value)
        else:
            # 如果key不存在，直接添加到字典中
            merged_dict[key] = value
    return merged_dict


def main() -> None:
    global BLDG

    parser = argparse.ArgumentParser(
        description="Merge/simplify a bridged Brick HVAC topology graph (VAV/CAV/RAD/FCU/"
                    "Pump/DH/AC/HX) into per-room virtual terminals, ready for Graph2BEM.")
    parser.add_argument("input", help="Input Turtle file (the bridge script's output, "
                                       "e.g. HVAC_topology_informative.ttl).")
    parser.add_argument("-o", "--output", default="HVAC_topology_BEM.ttl",
                         help="Output Turtle file path.")
    parser.add_argument("--namespace", default="urn:OPS#",
                         help="Instance namespace used by the input graph (must match the "
                              "bridge script's --namespace).")
    args = parser.parse_args()

    BLDG = Namespace(args.namespace)

    g_informative_topology = Graph()
    g_informative_topology.parse(args.input, format="turtle")
    g_informative_topology.bind("bldg", BLDG)
    print("Loaded %d triples from %s" % (len(g_informative_topology), args.input))

    # 1: Bridging the VAV and FCU
    g_informative_topology = bridge_VAV(g_informative_topology)

    # 2: Merging VAV
    g_informative_topology = merge_VAV(g_informative_topology)

    # 3: Merging Air diffusers without VAV
    g_informative_topology = merge_CAV(g_informative_topology)

    # 4: Merging RAD (not needs for openstudio SDK)
    g_informative_topology = merge_RAD(g_informative_topology)

    # 5: Merging FCU (not needs for openstudio SDK)
    g_informative_topology = merge_FCU(g_informative_topology)

    # 6: Merging Pump (not needs for openstudio SDK)
    g_informative_topology = merge_Pump(g_informative_topology)

    # 7: Merging DH (not needs for openstudio SDK)
    g_informative_topology = merge_DH(g_informative_topology)

    # 8: Merging AC (not needs for openstudio SDK)
    g_informative_topology = merge_AC(g_informative_topology)

    # 9: Merging HX (not needs for openstudio SDK)
    g_informative_topology = merge_HX(g_informative_topology)

    ### Done: Merge all the terminals in one type: RAD, DH, AC, VAV, Air_Diffuser

    g_informative_topology.serialize(args.output, format="ttl")
    print("Done with HVAC topology -> %s (%d triples)" % (args.output, len(g_informative_topology)))


if __name__ == "__main__":
    main()











