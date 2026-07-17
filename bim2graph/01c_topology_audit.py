"""Audits an IFC-to-Brick topology graph for connectivity gaps: equipment with
no connections at all, duct/pipe runs that dead-end where they shouldn't, and
(if a bridged graph with brick:Room is given) rooms nobody serves. Meant to run
on IFC_to_KG.py's Stage-1 output (which still carries fso:connectedWith - the
undirected, ground-truth "what's physically wired to what" picture) rather
than the bridged graph, since the bridge only keeps directed feeds/feedsAir
edges for classifiable equipment and drops connectedWith entirely.
"""
import argparse
from collections import defaultdict

import pandas as pd
from rdflib import RDF, Graph, Namespace, URIRef

BRICK = Namespace("https://brickschema.org/schema/Brick#")
FSO = Namespace("https://www.w3id.org/fso#")
PROPS = Namespace("https://w3id.org/props#")

# FSO classes that represent pure duct/pipe connectors, not real equipment -
# these should almost always have 2 connections (upstream + downstream); a
# degree of 1 usually means a missing/unmodeled connection, not a genuine
# dead end in the real building.
CONNECTOR_FSO_CLASSES = {"Segment", "Fitting", "TreatmentDevice"}

# Container/grouping types that are never expected to appear in
# fso:connectedWith by design - they're wired via hasComponent/hasPart/
# hasLocation instead of a physical port connection. Without this exclusion,
# every IfcSystem/IfcSite/IfcBuildingStorey/IfcSpace in a model shows up as
# "isolated" unconditionally, drowning out genuinely disconnected equipment
# (confirmed on real test data: 11/12 and 12/17 "isolated" rows were purely
# this, with only one real candidate - a pipe end-cap fitting - in either).
# Brick-side exclusion is by fragment suffix rather than an exact-match set,
# since mapping_IFC4.json emits many System subclasses (HVAC_System,
# Chilled_Water_System, Air_System, ...) all ending in "_System"/"System".
SPATIAL_BRICK_TYPES = {"Site", "Storey", "Space", "Room", "Zone", "Building"}
NON_PHYSICAL_FSO_TYPES = {"DistributionSystem"}


def load_types(g: Graph, namespace: Namespace) -> dict:
    types: dict = {}
    for s, _, o in g.triples((None, RDF.type, None)):
        if isinstance(o, URIRef) and str(o).startswith(str(namespace)):
            types.setdefault(s, set()).add(str(o)[len(str(namespace)):])
    return types


def get_name(g: Graph, node) -> str:
    for pred in (PROPS.hasName, PROPS.hasDescription):
        for _, _, o in g.triples((node, pred, None)):
            return str(o)
    return str(node).rsplit("#", 1)[-1]


def audit(g: Graph):
    brick_types = load_types(g, BRICK)
    fso_types = load_types(g, FSO)

    adjacency = defaultdict(set)
    for s, _, o in g.triples((None, FSO.connectedWith, None)):
        adjacency[s].add(o)
        adjacency[o].add(s)

    classified_nodes = set(brick_types.keys()) | set(fso_types.keys())
    connected_nodes = set(adjacency.keys())

    def is_physical(node) -> bool:
        f_types = fso_types.get(node, set())
        if f_types:
            # Has an FSO type: physical unless it's purely a System grouping.
            return not (f_types <= NON_PHYSICAL_FSO_TYPES)
        # No FSO type at all: physical unless it's purely a spatial container
        # (Site/Storey/Space/Room/Zone/Building - Brick types with no FSO
        # counterpart in the mapping tables).
        b_types = brick_types.get(node, set())
        return not (b_types and b_types <= SPATIAL_BRICK_TYPES)

    isolated_candidates = {n for n in (classified_nodes - connected_nodes) if is_physical(n)}

    isolated_rows = []
    for node in sorted(isolated_candidates, key=str):
        isolated_rows.append({
            "Node": str(node),
            "Name": get_name(g, node),
            "BrickTypes": ";".join(sorted(brick_types.get(node, set()))) or None,
            "FSOTypes": ";".join(sorted(fso_types.get(node, set()))) or None,
        })

    dead_end_rows = []
    for node in sorted(connected_nodes, key=str):
        if len(adjacency[node]) != 1:
            continue
        f_types = fso_types.get(node, set())
        if not (f_types & CONNECTOR_FSO_CLASSES):
            continue  # degree 1 is normal for most equipment/terminals
        neighbor = next(iter(adjacency[node]))
        dead_end_rows.append({
            "Node": str(node),
            "Name": get_name(g, node),
            "FSOTypes": ";".join(sorted(f_types)),
            "OnlyConnectionTo": get_name(g, neighbor),
        })

    # Connected components, to spot fragmented sub-networks.
    visited = set()
    components = []
    for start in connected_nodes:
        if start in visited:
            continue
        comp = set()
        stack = [start]
        visited.add(start)
        while stack:
            n = stack.pop()
            comp.add(n)
            for nb in adjacency[n]:
                if nb not in visited:
                    visited.add(nb)
                    stack.append(nb)
        components.append(comp)

    component_rows = []
    for comp in sorted(components, key=len, reverse=True):
        comp_brick_types = set()
        for n in comp:
            comp_brick_types |= brick_types.get(n, set())
        component_rows.append({
            "ComponentSize": len(comp),
            "BrickTypesPresent": ";".join(sorted(comp_brick_types)) or "(none classified)",
        })

    # Rooms with no incoming brick:feeds/feedsAir (only meaningful once fed a
    # bridged graph - Stage-1 output alone won't have these predicates).
    rooms = set(g.subjects(RDF.type, BRICK.Room))
    served_rooms = {o for _, p, o in g.triples((None, None, None))
                    if p in (BRICK.feeds, BRICK.feedsAir) and o in rooms}
    unserved_rows = [{"Room": str(r), "Name": get_name(g, r)} for r in sorted(rooms - served_rooms, key=str)]

    return {
        "total_classified": len(classified_nodes),
        "total_connected": len(connected_nodes),
        "isolated": isolated_rows,
        "dead_ends": dead_end_rows,
        "components": component_rows,
        "total_rooms": len(rooms),
        "unserved_rooms": unserved_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit a topology graph for connectivity gaps: isolated equipment, "
                     "dead-end duct/pipe runs, fragmented sub-networks, unserved rooms.")
    parser.add_argument("input", help="Turtle file - ideally IFC_to_KG.py's Stage-1 output "
                                       "(still has fso:connectedWith); a bridged graph also works "
                                       "for the isolated/dead-end/component checks but won't add "
                                       "anything for the room-service check beyond what's already there.")
    parser.add_argument("--out-prefix", default="topology_audit",
                         help="Prefix for the output CSV files (isolated/dead-ends/components/unserved-rooms).")
    args = parser.parse_args()

    g = Graph()
    g.parse(args.input, format="turtle")

    result = audit(g)
    print("Classified nodes: %d, connected (appear in fso:connectedWith): %d (%.0f%%)"
          % (result["total_classified"], result["total_connected"],
             100 * result["total_connected"] / result["total_classified"] if result["total_classified"] else 0))
    print("Isolated (classified but zero connections): %d" % len(result["isolated"]))
    print("Dead-end duct/pipe connectors (degree 1, should be 2): %d" % len(result["dead_ends"]))
    print("Connected components: %d" % len(result["components"]))
    print("Rooms: %d, unserved (no brick:feeds/feedsAir in this graph): %d"
          % (result["total_rooms"], len(result["unserved_rooms"])))

    for key, rows in [("isolated", result["isolated"]), ("dead_ends", result["dead_ends"]),
                       ("components", result["components"]), ("unserved_rooms", result["unserved_rooms"])]:
        if rows:
            path = "%s_%s.csv" % (args.out_prefix, key)
            pd.DataFrame(rows).to_csv(path, index=False)
            print("  -> %s (%d rows)" % (path, len(rows)))


if __name__ == "__main__":
    main()
