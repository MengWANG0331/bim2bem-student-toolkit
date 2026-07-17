#%% Import packages
import argparse
import json
import os

import ifcopenshell
import pandas as pd
from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef

MAPPING_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IFC = "Basement_East_Plantroom.ifc"
DEFAULT_OUTPUT = "Output.ttl"
DEFAULT_REVIEW_CSV = "classification_review.csv"
DEFAULT_CONNECTIVITY_REVIEW_CSV = "connectivity_review.csv"

OM = Namespace("https://openmetrics.eu/openmetrics#")
BOT = Namespace("https://w3id.org/bot#")
BRICK = Namespace("https://brickschema.org/schema/Brick#")
FSO = Namespace("https://www.w3id.org/fso#")
PROPS = Namespace("https://w3id.org/props#")
REF = Namespace("https://w3id.org/brick/ref#")

# Confidence tiers for the human-review report, worst (most in need of review) first.
CONFIDENCE_ORDER = {
    "unmapped": 0,
    "generic_ancestor": 1,
    "generic_own_type": 2,
    "specific_ancestor": 3,
    "specific": 4,
}


def OM_inst(component: ifcopenshell.entity_instance) -> URIRef:
    return OM["inst_" + component.GlobalId.replace("$", "_")]


#%% Mapping table helpers


def load_mapping(f: ifcopenshell.file) -> dict:
    schema = f.wrapped_data.schema
    if schema == "IFC2X3":
        path = os.path.join(MAPPING_DIR, "mapping_IFC2x3.json")
    elif schema == "IFC4":
        path = os.path.join(MAPPING_DIR, "mapping_IFC4.json")
    else:
        raise SystemExit(f"Not supporting IFC schema version: {schema}")
    print("Version: " + schema)
    with open(path) as fh:
        return json.load(fh)


def index_mapping(mapping: dict) -> dict:
    """Group flat 'IfcType' / 'IfcType.PREDEFINEDTYPE' keys into
    {base_ifc_type: {predefined_type_or_None: entry}}."""
    by_base: dict = {}
    for key, entry in mapping.items():
        dot_pos = key.find(".")
        if dot_pos > 0:
            base, predefined = key[:dot_pos], key[dot_pos + 1:]
        else:
            base, predefined = key, None
        by_base.setdefault(base, {})[predefined] = entry
    return by_base


def classify_element(element: ifcopenshell.entity_instance, by_base: dict):
    """Pick the mapping entry group for an element: its own exact IFC class if
    the table defines one, otherwise the closest mapped ancestor class. This
    keeps a concrete leaf type (e.g. IfcBoiler) from also being re-tagged by
    an abstract supertype entry (e.g. IfcEnergyConversionDevice) that also
    matches it, since ifcopenshell's by_type() includes subtypes."""
    own_type = element.is_a()
    if own_type in by_base:
        return own_type, by_base[own_type]
    for base_type, variants in by_base.items():
        try:
            if element.is_a(base_type):
                return base_type, variants
        except Exception:
            continue
    return None, None


#%% Converter

#####################################################################################
###############     TRANSFORM and LOAD product IFC instances      ##################
#####################################################################################


def transform_and_load(f: ifcopenshell.file, graph: Graph, by_base: dict) -> list:
    """Classify every mapped IFC element into the graph. Returns one review
    row per candidate element (GlobalId, type info, assigned Brick class,
    and a confidence tier) for the human-review CSV."""
    print("Mapping IFC entities to Knowledge Graph...")

    elements_by_guid = {}
    for base_type in by_base:
        for element in f.by_type(base_type):
            elements_by_guid[element.GlobalId] = element

    review_rows = []
    for element in elements_by_guid.values():
        own_type = element.is_a()
        predefined = getattr(element, "PredefinedType", None)
        matched_base, variants = classify_element(element, by_base)

        entry = None
        confidence = "unmapped"
        if matched_base is not None:
            specific_entry = variants.get(predefined)
            if predefined is not None and specific_entry is not None:
                entry = specific_entry
                confidence = "specific" if matched_base == own_type else "specific_ancestor"
            else:
                entry = variants.get(None)
                confidence = "generic_own_type" if matched_base == own_type else "generic_ancestor"

        if entry is None:
            review_rows.append({
                "GlobalId": element.GlobalId,
                "Name": element.Name,
                "IfcType": own_type,
                "PredefinedType": predefined,
                "BrickClass": None,
                "Confidence": "unmapped",
            })
            continue

        inst = OM_inst(element)
        graph.add((inst, REF.IFCReference, Literal(element.GlobalId, datatype=XSD.string)))
        name = element.Name or ""
        if element.Description:
            graph.add((inst, PROPS.hasDescription, Literal(name + " / " + element.Description, datatype=XSD.string)))
        else:
            graph.add((inst, PROPS.hasName, Literal(name, datatype=XSD.string)))

        brick_class = entry.get("brick") or None
        if entry.get("bot"):
            graph.add((inst, RDF.type, URIRef(BOT + entry["bot"])))
        if entry.get("fso"):
            graph.add((inst, RDF.type, URIRef(FSO + entry["fso"])))
        if brick_class:
            graph.add((inst, RDF.type, URIRef(BRICK + brick_class)))
        graph.add((inst, PROPS.hasClassificationConfidence, Literal(confidence, datatype=XSD.string)))

        review_rows.append({
            "GlobalId": element.GlobalId,
            "Name": element.Name,
            "IfcType": own_type,
            "PredefinedType": predefined,
            "BrickClass": brick_class,
            "Confidence": confidence,
        })

    mapped = sum(1 for r in review_rows if r["Confidence"] != "unmapped")
    print("All IFC entities have been mapped to KG! (%d classified, %d unmapped out of %d candidate elements)"
          % (mapped, len(review_rows) - mapped, len(review_rows)))
    return review_rows


#########################################################################################
############################     Create Relationships      ##############################
#########################################################################################


def resolve_flow_direction(direction: str, port_name: str):
    """Classify a RelatedPort's flow role as 'sink', 'source', or None (genuinely
    undetermined). SOURCEANDSINK ports are disambiguated by port-name prefix,
    matched case-insensitively since real-world IFC exports vary in capitalization
    (e.g. 'InPort_123' vs 'Inport_123' vs 'inport_123' depending on the authoring
    tool) — a plain case-sensitive prefix check silently drops the majority of
    SOURCEANDSINK ports on some exports."""
    name = (port_name or "").lower()
    if direction == "SINK" or (direction == "SOURCEANDSINK" and name.startswith("inport")):
        return "sink"
    if direction == "SOURCE" or (direction == "SOURCEANDSINK" and name.startswith("outport")):
        return "source"
    return None


def build_port_host_map(f: ifcopenshell.file) -> dict:
    """Maps each IfcDistributionPort to its host element, handling both
    schema-version mechanisms: IFC2X3's explicit IfcRelConnectsPortToElement
    relationship (no .Nests inverse attribute exists in IFC2X3 at all - it's
    IFC4-only), and IFC4's generalized IfcRelNests inverse (.Nests) attribute
    on the port. Some IFC4 exporters still emit the older PortToElement
    relationship too, so both are checked regardless of declared schema."""
    host_by_port = {}
    for rel in f.by_type("IfcRelConnectsPortToElement"):
        host_by_port[rel.RelatingPort] = rel.RelatedElement
    for port in f.by_type("IfcDistributionPort"):
        if port in host_by_port:
            continue
        nests = getattr(port, "Nests", None)
        if nests:
            host_by_port[port] = nests[0].RelatingObject
    return host_by_port


def build_relationships(f: ifcopenshell.file, graph: Graph) -> list:
    """Wires up connectivity/topology triples. Returns one review row per port
    connection whose flow direction couldn't be determined from FlowDirection +
    port name — those get a bidirectional feedsFluidTo fallback (so the graph
    stays maximally connected/automatable for students) instead of silently
    losing the direction, flagged here for manual correction."""
    print("1st step: Distribution Ports processing...")

    connectivity_review_rows = []
    port_host_map = build_port_host_map(f)

    # 1. Distribution component Ports for connectivity of components (using BOT, FSO)
    for connection in f.by_type("IFCRELCONNECTSPORTS"):
        component_1 = port_host_map.get(connection.RelatedPort)
        component_2 = port_host_map.get(connection.RelatingPort)
        if component_1 is None or component_2 is None:
            continue  # orphan port, no host element relationship found
        graph.add((OM_inst(component_1), FSO.connectedWith, OM_inst(component_2)))

        direction = connection.RelatedPort.FlowDirection
        port_name = connection.RelatedPort.Name or ""
        role = resolve_flow_direction(direction, port_name)

        # role describes component_1's own port: a "sink" port receives fluid,
        # so the physical flow is component_2 -> component_1 (verified against
        # real data: a boiler's real SINK-flagged port connects to a pipe
        # segment's SOURCE port, and the pipe feeds the boiler, not the other
        # way around). A "source" port emits, so component_1 -> component_2.
        if role == "sink":
            graph.add((OM_inst(component_2), FSO.feedsFluidTo, OM_inst(component_1)))
        elif role == "source":
            graph.add((OM_inst(component_1), FSO.feedsFluidTo, OM_inst(component_2)))
        else:
            # Direction undetermined: fall back to bidirectional so downstream
            # traversal/automation doesn't lose the connection entirely, and
            # flag it so a student can pick the real direction by hand.
            graph.add((OM_inst(component_1), FSO.feedsFluidTo, OM_inst(component_2)))
            graph.add((OM_inst(component_2), FSO.feedsFluidTo, OM_inst(component_1)))
            connectivity_review_rows.append({
                "Component1_GlobalId": component_1.GlobalId,
                "Component1_Name": component_1.Name,
                "Component1_IfcType": component_1.is_a(),
                "Component2_GlobalId": component_2.GlobalId,
                "Component2_Name": component_2.Name,
                "Component2_IfcType": component_2.is_a(),
                "RelatedPort_FlowDirection": direction,
                "RelatedPort_Name": port_name,
                "Resolution": "bidirectional_fallback",
            })

    print("2nd step: System groups processing...")

    # 2. Systems from grouped elements - IfcSystems need to be generated from enrichment processes
    for system in f.by_type("IfcSystem"):
        if not system.IsGroupedBy:
            continue  # system has no grouped members
        for comp in system.IsGroupedBy[0].RelatedObjects:
            if comp.is_a() != "IfcDistributionPort":
                graph.add((OM_inst(system), FSO.hasComponent, OM_inst(comp)))
                graph.add((OM_inst(system), BRICK.hasPart, OM_inst(comp)))

    print("3rd step: Topology processing...")

    # Topological relationships (brick:hasLocation) + properties
    for space in f.by_type("IfcSpace"):
        if not space.Decomposes:
            continue  # space isn't assigned to a storey
        storey = space.Decomposes[0].RelatingObject
        if not storey.Decomposes:
            continue  # storey isn't assigned to a building
        building = storey.Decomposes[0].RelatingObject
        graph.add((OM_inst(building), BOT.hasStorey, OM_inst(storey)))
        graph.add((OM_inst(building), BRICK.hasPart, OM_inst(storey)))
        graph.add((OM_inst(storey), BOT.hasSpace, OM_inst(space)))
        graph.add((OM_inst(storey), BRICK.hasPart, OM_inst(space)))
        for prop in space.IsDefinedBy:
            try:  # try and find area and volume properties in spaces (if they exist)
                for q in prop.RelatingPropertyDefinition.Quantities:
                    if q.is_a() == "IfcQuantityVolume":
                        graph.add((OM_inst(space), BRICK.volume, Literal(q.VolumeValue, datatype=XSD.decimal)))
                    if q.is_a() == "IfcQuantityArea":
                        graph.add((OM_inst(space), BRICK.area, Literal(q.AreaValue, datatype=XSD.decimal)))
            except AttributeError:
                pass

    print("4th step: Spatial containment processing...")

    # Spatial Containment of elements/components
    for containment in f.by_type("IFCRELCONTAINEDINSPATIALSTRUCTURE"):
        if containment.RelatingStructure.is_a() == "IfcSpace":
            space = containment.RelatingStructure
            for element in containment.RelatedElements:
                graph.add((OM_inst(space), BOT.hasElement, OM_inst(element)))
                graph.add((OM_inst(element), BRICK.hasLocation, OM_inst(space)))

    return connectivity_review_rows


#%% Entry point


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert an IFC model into a Brick/BOT/FSO knowledge graph.")
    parser.add_argument("ifc_path", nargs="?", default=DEFAULT_IFC, help="Path to the input IFC file.")
    parser.add_argument("-o", "--output", default=DEFAULT_OUTPUT, help="Output Turtle file path.")
    parser.add_argument("--review-csv", default=DEFAULT_REVIEW_CSV,
                         help="Path for the human-review CSV (per-instance classification confidence).")
    parser.add_argument("--connectivity-review-csv", default=DEFAULT_CONNECTIVITY_REVIEW_CSV,
                         help="Path for the human-review CSV (port connections with undetermined flow direction).")
    args = parser.parse_args()

    graph = Graph()
    graph.namespace_manager.bind("om", OM)
    graph.namespace_manager.bind("bot", BOT)
    graph.namespace_manager.bind("brick", BRICK)
    graph.namespace_manager.bind("rdf", RDF)
    graph.namespace_manager.bind("ref", REF)
    graph.namespace_manager.bind("props", PROPS)
    graph.namespace_manager.bind("xsd", XSD)
    graph.namespace_manager.bind("fso", FSO)

    print("Importing IFC...")
    f = ifcopenshell.open(args.ifc_path)
    by_base = index_mapping(load_mapping(f))

    review_rows = transform_and_load(f, graph, by_base)
    connectivity_review_rows = build_relationships(f, graph)

    print("DONE")

    #%% Export the graph
    graph.serialize(destination=args.output, format="turtle")
    print("Results exported in " + args.output)

    review_df = pd.DataFrame(review_rows)
    review_df["_sort"] = review_df["Confidence"].map(CONFIDENCE_ORDER)
    review_df = review_df.sort_values("_sort").drop(columns="_sort")
    review_df.to_csv(args.review_csv, index=False)
    flagged = int((review_df["Confidence"] != "specific").sum())
    print("Review report written to %s (%d/%d rows flagged for manual review)"
          % (args.review_csv, flagged, len(review_df)))

    if connectivity_review_rows:
        pd.DataFrame(connectivity_review_rows).to_csv(args.connectivity_review_csv, index=False)
        print("Connectivity review report written to %s (%d port connection(s) fell back to "
              "bidirectional feedsFluidTo and need manual direction correction)"
              % (args.connectivity_review_csv, len(connectivity_review_rows)))
    else:
        print("All port connections had a determinable flow direction - no connectivity review needed.")


if __name__ == "__main__":
    main()
