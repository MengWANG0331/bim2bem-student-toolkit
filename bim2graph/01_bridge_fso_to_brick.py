"""Bridges an IFC-to-Brick FSO/Brick topology graph (IFC_to_KG.py's output) into
the Brick-relation topology (brick:feeds / brick:feedsAir, brick:Room) that the
rest of Graph-to-BEM (Topology2BEM_2/3/4) expects. IFC_to_KG.py emits FSO-namespace
relationship predicates (fso:connectedWith, fso:feedsFluidTo, fso:hasComponent) and
types spaces as brick:Space; Graph-to-BEM queries brick:feeds/brick:feedsAir directly
and matches brick:Room by exact type (no subClassOf reasoning) - neither side needs
to change, this script translates between them.
"""
import argparse

import pandas as pd
from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef

OM = Namespace("https://openmetrics.eu/openmetrics#")
BOT = Namespace("https://w3id.org/bot#")
BRICK = Namespace("https://brickschema.org/schema/Brick#")
FSO = Namespace("https://www.w3id.org/fso#")
PROPS = Namespace("https://w3id.org/props#")

DEFAULT_INPUT = "Output.ttl"
DEFAULT_OUTPUT = "HVAC_topology_informative.ttl"
DEFAULT_NAMESPACE = "urn:OPS#"
DEFAULT_REVIEW_CSV = "bridge_review.csv"
DEFAULT_ZONE_NAME_REVIEW_CSV = "zone_name_review.csv"

# Classifies Brick classes into air-side vs water-side, to disambiguate a
# direction-only fso:feedsFluidTo edge into brick:feedsAir vs brick:feeds.
# Extend this as IFC-to-Brick's mapping tables (mapping_IFC4.json /
# mapping_IFC2x3.json) gain coverage for classes Graph-to-BEM also expects but
# that aren't mapped from any IFC type yet as of 2026-07-16: FCU, MVHR, DH, AC,
# Chilled_Water_Pump, Hot_Water_Pump (currently only generic "Pump" exists).
AIR_SIDE_CLASSES = {
    "AHU", "VAV", "CAV", "RTU", "MVHR", "Air_Diffuser", "FCU",
    "Air_System", "Ventilation_Air_System", "Fan", "Damper", "Relief_Damper",
    "Filter", "Humidifier", "Heat_Wheel",
}
WATER_SIDE_CLASSES = {
    "Pump", "Chilled_Water_Pump", "Hot_Water_Pump", "Radiator", "Space_Heater",
    "Heat_Exchanger", "HX", "Chiller", "Boiler", "Valve", "Coil",
    "Cooling_Coil", "Heating_Coil", "Chilled_Water_Coil", "Hot_Water_Coil",
    "Chilled_Water_System", "Domestic_Hot_Water_System", "Water_System",
    "Cooling_Tower", "Condenser", "AC", "DH", "Active_Chilled_Beam",
    "Passive_Chilled_Beam", "Chilled_Beam", "Water_Tank",
}


def load_brick_types(g: Graph) -> dict:
    """subject -> set of Brick-namespace type fragments (e.g. {'AHU'})."""
    types: dict = {}
    for s, _, o in g.triples((None, RDF.type, None)):
        if isinstance(o, URIRef) and str(o).startswith(str(BRICK)):
            types.setdefault(s, set()).add(str(o)[len(str(BRICK)):])
    return types


def classify_side(type_set: set):
    if type_set & WATER_SIDE_CLASSES:
        return "water"
    if type_set & AIR_SIDE_CLASSES:
        return "air"
    return None


def propagate_sides(g_in: Graph, types: dict) -> dict:
    """Seeds air/water classification from Brick-typed equipment, then floods
    it across fso:connectedWith (undirected port connectivity) to unclassified
    connector elements - duct/pipe Segment and Fitting instances, which
    mapping_IFC4.json/mapping_IFC2x3.json assign an fso type but no Brick
    class to (see module docstring). A contiguous run of duct/pipework is
    essentially never mixed-medium, so this is safe to propagate through.
    Returns {node: 'air'|'water'} for every node reachable from a seed;
    unreachable/still-ambiguous nodes are simply absent."""
    adjacency: dict = {}
    for s, _, o in g_in.triples((None, FSO.connectedWith, None)):
        adjacency.setdefault(s, set()).add(o)
        adjacency.setdefault(o, set()).add(s)

    sides = {}
    conflicted = set()
    queue = []
    for node, type_set in types.items():
        side = classify_side(type_set)
        if side is not None:
            sides[node] = side
            queue.append(node)

    while queue:
        node = queue.pop()
        if node not in sides:
            # Was queued as a seed/propagation target, but later reached from
            # a conflicting air/water path and deleted from `sides` below
            # before its own turn came up.
            continue
        for neighbor in adjacency.get(node, ()):
            if neighbor in conflicted:
                continue
            existing = sides.get(neighbor)
            if existing is None:
                sides[neighbor] = sides[node]
                queue.append(neighbor)
            elif existing != sides[node]:
                # Reached from both an air-side and a water-side seed - the
                # topology is ambiguous here, don't guess.
                del sides[neighbor]
                conflicted.add(neighbor)

    return sides


def remap(term, target_ns: Namespace):
    """Rewrite an om:inst_<id> instance URI into <target_ns><id>. Brick/BOT/FSO
    vocabulary terms and non-URIRef terms (e.g. Literals) pass through unchanged."""
    if not isinstance(term, URIRef):
        return term
    value = str(term)
    if not value.startswith(str(OM)):
        return term
    fragment = value[len(str(OM)):]
    if fragment.startswith("inst_"):
        fragment = fragment[len("inst_"):]
    return target_ns[fragment]


def bridge(g_in: Graph, namespace: str):
    target_ns = Namespace(namespace)
    g_out = Graph()
    g_out.namespace_manager.bind("bldg", target_ns)
    g_out.namespace_manager.bind("brick", BRICK)
    g_out.namespace_manager.bind("bot", BOT)

    types = load_brick_types(g_in)
    sides = propagate_sides(g_in, types)
    fso_predicates = (FSO.connectedWith, FSO.feedsFluidTo, FSO.hasComponent)

    # 1. Carry over everything except the FSO relationship predicates
    #    (rdf:type, PROPS.*, REF.IFCReference, BOT/BRICK space-containment
    #    triples already emitted by IFC_to_KG.py), remapping instance URIs.
    for s, p, o in g_in:
        if p in fso_predicates:
            continue
        g_out.add((remap(s, target_ns), p, remap(o, target_ns)))

    # 2. brick:Space instances also get brick:Room: Graph-to-BEM matches
    #    brick:Room by exact type with no subClassOf reasoning applied.
    #    Each Room also gets an explicit, human-editable props:hasIDFZoneName
    #    literal - simulation_HVACTemplate should match zones against this
    #    property exactly, rather than guessing from the room URI's own
    #    fragment. Defaults to that fragment as a placeholder (a no-op until
    #    someone corrects it) and is listed in zone_name_review_rows so a
    #    human can confirm/fix it against the real target IDF - this is a
    #    graph-authoring/review-stage responsibility, not something the HVAC
    #    code should reach into the geometry pipeline to resolve itself.
    zone_name_review_rows = []
    for s, type_set in types.items():
        if "Space" in type_set:
            room_uri = remap(s, target_ns)
            placeholder_zone_name = str(room_uri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            g_out.add((room_uri, RDF.type, BRICK.Room))
            g_out.add((room_uri, PROPS.hasIDFZoneName, Literal(placeholder_zone_name, datatype=XSD.string)))
            zone_name_review_rows.append({
                "Room": str(room_uri),
                "PlaceholderIDFZoneName": placeholder_zone_name,
                "MatchesKnownIDFZone": None,
            })

    # 3. fso:hasComponent (system/group membership) -> brick:hasPart.
    for s, p, o in g_in.triples((None, FSO.hasComponent, None)):
        g_out.add((remap(s, target_ns), BRICK.hasPart, remap(o, target_ns)))

    # 4. fso:feedsFluidTo -> brick:feeds (water) / brick:feedsAir (air),
    #    disambiguated by whichever endpoint's Brick type is classifiable.
    #    Undetermined edges default to brick:feeds and get flagged for review
    #    rather than silently guessed, mirroring IFC_to_KG.py's connectivity
    #    review-CSV pattern.
    review_rows = []
    for s, p, o in g_in.triples((None, FSO.feedsFluidTo, None)):
        side = sides.get(s) or sides.get(o)
        predicate = BRICK.feedsAir if side == "air" else BRICK.feeds
        if side is None:
            review_rows.append({
                "Subject": str(s), "SubjectTypes": ";".join(sorted(types.get(s, set()))) or None,
                "Object": str(o), "ObjectTypes": ";".join(sorted(types.get(o, set()))) or None,
                "Resolution": "defaulted_to_feeds_undetermined_side",
            })
        g_out.add((remap(s, target_ns), predicate, remap(o, target_ns)))

    return g_out, review_rows, zone_name_review_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Bridge an IFC-to-Brick FSO/Brick output graph into the "
                     "Brick-relation topology Graph-to-BEM's HVAC scripts expect.")
    parser.add_argument("input", nargs="?", default=DEFAULT_INPUT,
                         help="Input Turtle file (IFC_to_KG.py's output).")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="Output Turtle file path.")
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE,
                         help="Target instance namespace (default matches Topology2BEM_2's expected input).")
    parser.add_argument("--review-csv", default=DEFAULT_REVIEW_CSV,
                         help="Path for the human-review CSV (feedsFluidTo edges with an undetermined air/water side).")
    parser.add_argument("--zone-name-review-csv", default=DEFAULT_ZONE_NAME_REVIEW_CSV,
                         help="Path for the human-review CSV listing each Room's placeholder IDF zone name.")
    parser.add_argument("--idf", help="Optional target IDF file - if given (with --idd), the zone-name review "
                                       "CSV cross-checks each Room's placeholder against the IDF's real zone "
                                       "names and lists the available zone names for reference. Without this, "
                                       "the review CSV still lists placeholders to be checked by hand.")
    parser.add_argument("--idd", help="Path to EnergyPlus's Energy+.idd, required if --idf is given.")
    args = parser.parse_args()

    g_in = Graph()
    g_in.parse(args.input, format="turtle")
    print("Loaded %d triples from %s" % (len(g_in), args.input))

    g_out, review_rows, zone_name_review_rows = bridge(g_in, args.namespace)
    g_out.serialize(destination=args.output, format="turtle")
    print("Bridged graph written to %s (%d triples)" % (args.output, len(g_out)))

    if review_rows:
        pd.DataFrame(review_rows).to_csv(args.review_csv, index=False)
        print("Review report written to %s (%d feedsFluidTo edge(s) had an undetermined air/water side)"
              % (args.review_csv, len(review_rows)))
    else:
        print("All feedsFluidTo edges had a determinable air/water side - no bridge review needed.")

    if zone_name_review_rows:
        idf_zone_names = None
        if args.idf:
            if not args.idd:
                raise SystemExit("--idd is required when --idf is given.")
            from eppy.modeleditor import IDF
            IDF.setiddname(args.idd)
            idf_zone_names = sorted(zone.Name for zone in IDF(args.idf).idfobjects["ZONE"])

        unmatched = 0
        for row in zone_name_review_rows:
            if idf_zone_names is None:
                row["MatchesKnownIDFZone"] = "unknown (no --idf given)"
            elif row["PlaceholderIDFZoneName"] in idf_zone_names:
                row["MatchesKnownIDFZone"] = "yes"
            else:
                row["MatchesKnownIDFZone"] = "NO - pick from AvailableIDFZoneNames"
                unmatched += 1
            row["AvailableIDFZoneNames"] = "; ".join(idf_zone_names) if idf_zone_names is not None else None

        pd.DataFrame(zone_name_review_rows).to_csv(args.zone_name_review_csv, index=False)
        if idf_zone_names is None:
            print("Zone-name review report written to %s (%d Room(s) - pass --idf/--idd to auto-cross-check "
                  "against a real IDF's zone names)" % (args.zone_name_review_csv, len(zone_name_review_rows)))
        else:
            print("Zone-name review report written to %s (%d/%d Room(s) did not match any IDF zone name and "
                  "need a manual props:hasIDFZoneName correction in the graph)"
                  % (args.zone_name_review_csv, unmatched, len(zone_name_review_rows)))


if __name__ == "__main__":
    main()
