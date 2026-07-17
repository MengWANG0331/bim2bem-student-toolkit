"""Collapses pass-through duct/pipe connector nodes out of a merged HVAC
topology graph (Topology2BEM_2's output), leaving only direct brick:feeds/
feedsAir edges between real components (Boiler/Pump/Valve/Radiator/HX/... -
anything IFC-to-Brick's mapping tables gave a real Brick class to).

Neither IFC_to_KG.py nor Topology2BEM_2 strip these out: duct/pipe segments
and fittings (IfcDuctSegment/IfcDuctFitting/IfcDuctSilencer/IfcPipeSegment/
IfcPipeFitting) get an fso type but a deliberately empty Brick class in
mapping_IFC4.json/mapping_IFC2x3.json, so they carry no semantic identity of
their own - they're just wiring. A real building can have dozens of these
between two pieces of real equipment (confirmed on real test data: a boiler
reaches its radiators 41-51 hops away, almost entirely pipe segments/fittings/
valves), which makes the raw or merged graph unreadable for a human and
unnecessary for anything that only cares about "what feeds what" at the
component level - use this after Topology2BEM_2 to get the graph fully into a
"just the boxes and arrows a person would draw on a whiteboard" shape.

A node is treated as a pass-through connector if it has an fso type but no
Brick type at all - this deliberately keeps nodes that DO have an fso
connector-family type but also a real Brick class (e.g. IfcFilter is
fso:TreatmentDevice + brick:Filter) since those have real equipment identity,
just collapses the ones IFC-to-Brick left un-typed on the Brick side.
"""
import argparse
from collections import defaultdict, deque

from rdflib import RDF, XSD, Graph, Literal, Namespace, URIRef

BRICK = Namespace("https://brickschema.org/schema/Brick#")
BOT = Namespace("https://w3id.org/bot#")
FSO = Namespace("https://www.w3id.org/fso#")
PROPS = Namespace("https://w3id.org/props#")

FEEDS_PREDICATES = (BRICK.feeds, BRICK.feedsAir)

# Kept alongside rdf:type and the feeds/feedsAir edges: real names/labels and
# structural containment ("connections" in the loose sense the user cares
# about), not Stage1's own bookkeeping (ref:IFCReference, the classification-
# confidence tier, or brick:area/volume quantities) - those stay in merged.ttl
# for anyone who needs to trace back to the source IFC, but clutter a graph
# meant to be read as "just the boxes and arrows."
KEEP_METADATA_PREDICATES = {
    PROPS.hasName, PROPS.hasDescription, PROPS.hasIDFZoneName,
    BRICK.hasPart, BOT.hasSpace, BOT.hasStorey,
}


def plain(term):
    """IFC_to_KG.py constructs every literal with an explicit datatype=XSD.string,
    so Turtle serializes them as e.g. "Erdgeschoss"^^xsd:string instead of the
    bare "Erdgeschoss" - correct RDF, but noisy for a graph meant to be read by
    a human. Since xsd:string is RDF 1.1's default literal datatype anyway,
    dropping the explicit tag loses no information."""
    if isinstance(term, Literal) and term.datatype == XSD.string:
        return Literal(str(term))
    return term


def load_types(g: Graph, namespace: Namespace) -> dict:
    types: dict = {}
    for s, _, o in g.triples((None, RDF.type, None)):
        if isinstance(o, URIRef) and str(o).startswith(str(namespace)):
            types.setdefault(s, set()).add(str(o)[len(str(namespace)):])
    return types


def collapse(g_in: Graph):
    brick_types = load_types(g_in, BRICK)
    fso_types = load_types(g_in, FSO)

    def is_connector(node) -> bool:
        return bool(fso_types.get(node)) and not brick_types.get(node)

    adjacency = defaultdict(list)  # node -> [(predicate, target), ...]
    for pred in FEEDS_PREDICATES:
        for s, _, o in g_in.triples((None, pred, None)):
            adjacency[s].append((pred, o))

    real_nodes = {n for n in set(brick_types) | set(fso_types) if not is_connector(n)}

    g_out = Graph()
    g_out.namespace_manager.bind("brick", BRICK)

    # Carry over every triple that doesn't involve a connector node as subject
    # or object, and isn't itself a feeds/feedsAir edge (those get rebuilt
    # below via the collapsed traversal, to avoid duplicating direct edges
    # that don't cross any connector).
    for s, p, o in g_in:
        if p in FEEDS_PREDICATES:
            continue
        if is_connector(s) or is_connector(o):
            continue
        if p != RDF.type and p not in KEEP_METADATA_PREDICATES:
            continue
        g_out.add((s, p, plain(o)))

    collapsed_edges = set()
    n_connectors_collapsed = 0
    for start in real_nodes:
        for pred, first_hop in adjacency.get(start, ()):
            queue = deque([first_hop])
            seen_hops = {first_hop}
            while queue:
                node = queue.popleft()
                if is_connector(node):
                    n_connectors_collapsed += 1
                    for _, nxt in adjacency.get(node, ()):
                        if nxt not in seen_hops:
                            seen_hops.add(nxt)
                            queue.append(nxt)
                else:
                    collapsed_edges.add((start, pred, node))

    for s, p, o in collapsed_edges:
        g_out.add((s, p, o))

    return g_out, len(real_nodes), len(collapsed_edges), n_connectors_collapsed


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Collapse pass-through duct/pipe Segment/Fitting nodes out of a merged "
                    "HVAC topology graph, leaving only direct component-to-component feeds/feedsAir edges.")
    parser.add_argument("input", help="Merged Turtle file (Topology2BEM_2's output).")
    parser.add_argument("-o", "--output", default="component_topology.ttl",
                         help="Output Turtle file path.")
    args = parser.parse_args()

    g_in = Graph()
    g_in.parse(args.input, format="turtle")
    print("Loaded %d triples from %s" % (len(g_in), args.input))

    g_out, n_real, n_edges, n_collapsed_visits = collapse(g_in)
    g_out.serialize(destination=args.output, format="turtle")
    print("Component-level graph written to %s (%d triples): %d real components, "
          "%d direct feeds/feedsAir edges (passed through %d connector-node hops total)"
          % (args.output, len(g_out), n_real, n_edges, n_collapsed_visits))


if __name__ == "__main__":
    main()
