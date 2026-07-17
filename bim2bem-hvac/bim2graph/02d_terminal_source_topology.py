"""Reduces a merged HVAC topology graph (Topology2BEM_2's output) down to just
the two node kinds a person actually cares about when asking "what feeds
what": heat/cold sources (Boiler/Chiller/Cooling_Tower) and terminal units
(Radiator/Space_Heater/FCU/VAV/CAV/DH/AC/Air_Diffuser) - everything else
(pumps, valves, HX, ductwork, Systems, Site/Storey) is dropped entirely, not
just collapsed-through like CollapseConnectors.py does.

Also replaces every kept node's GUID-based identifier with a short readable
tag (Boiler-1, Radiator-3, ...), the same idea as the user's older, manually-
curated BIM2BEM_topology_simplification_waterloop.py (which read a hand-built
GUID->"Emark" tag table, e.g. "TW00-UR-RAD-004"), but derived automatically
here since Stage1 already carries each element's own IFC Name/Description.

Reuses the source->terminal BFS from SourceTrace.py (same direction-fixed
brick:feeds/feedsAir traversal skipping through every intermediate pump/
valve/pipe node), so this only needs the port-connectivity graph - no
element-to-space spatial data required, unlike terminal->room assignment.
"""
import argparse
from collections import defaultdict, deque

from rdflib import RDF, Graph, Literal, Namespace, URIRef

BRICK = Namespace("https://brickschema.org/schema/Brick#")
PROPS = Namespace("https://w3id.org/props#")

SOURCE_CLASSES = {"Boiler", "Chiller", "Cooling_Tower"}
TERMINAL_CLASSES = {
    "Radiator", "Space_Heater", "FCU", "VAV", "CAV", "DH", "AC", "Air_Diffuser",
}
FEEDS_PREDICATES = (BRICK.feeds, BRICK.feedsAir)


def load_types(g: Graph) -> dict:
    types: dict = {}
    for s, _, o in g.triples((None, RDF.type, None)):
        if isinstance(o, URIRef) and str(o).startswith(str(BRICK)):
            types.setdefault(s, set()).add(str(o)[len(str(BRICK)):])
    return types


def own_label(g: Graph, node) -> str:
    """The original hasName/hasDescription, if any - kept as a label on the
    renamed node so a human can still tell two same-typed instances apart."""
    for pred in (PROPS.hasName, PROPS.hasDescription):
        for _, _, o in g.triples((node, pred, None)):
            return str(o)
    return None


def assign_tags(nodes_by_type: dict, namespace: Namespace) -> dict:
    """node -> new short URI, e.g. Boiler-1, Radiator-3. Stable ordering by
    original GUID fragment so re-runs on the same input produce the same tags."""
    tag_of = {}
    for type_name, nodes in nodes_by_type.items():
        for i, node in enumerate(sorted(nodes, key=str), start=1):
            tag_of[node] = namespace["%s-%d" % (type_name, i)]
    return tag_of


def build(g_in: Graph, namespace: str):
    ns = Namespace(namespace)
    types = load_types(g_in)

    sources_by_type = defaultdict(list)
    terminals_by_type = defaultdict(list)
    for node, node_types in types.items():
        hit = node_types & SOURCE_CLASSES
        if hit:
            sources_by_type[next(iter(hit))].append(node)
        hit = node_types & TERMINAL_CLASSES
        if hit:
            terminals_by_type[next(iter(hit))].append(node)

    tag_of = assign_tags(sources_by_type, ns)
    tag_of.update(assign_tags(terminals_by_type, ns))

    adjacency = defaultdict(list)  # node -> [(predicate, target), ...]
    for pred in FEEDS_PREDICATES:
        for s, _, o in g_in.triples((None, pred, None)):
            adjacency[s].append((pred, o))

    g_out = Graph()
    g_out.namespace_manager.bind("bldg", ns)
    g_out.namespace_manager.bind("brick", BRICK)
    g_out.namespace_manager.bind("props", PROPS)

    all_terminals = {n for terms in terminals_by_type.values() for n in terms}
    all_sources = {n for srcs in sources_by_type.values() for n in srcs}

    for type_name, nodes in list(sources_by_type.items()) + list(terminals_by_type.items()):
        for node in nodes:
            tag = tag_of[node]
            g_out.add((tag, RDF.type, BRICK[type_name]))
            label = own_label(g_in, node)
            if label:
                g_out.add((tag, PROPS.hasDescription, Literal(label)))

    n_edges = 0
    reached_terminals = set()
    for source in all_sources:
        depth = {source: 0}
        queue = deque([(source, None)])  # (node, predicate that got us here from source)
        entry_pred = {}
        while queue:
            node, _ = queue.popleft()
            for pred, neighbor in adjacency.get(node, ()):
                if neighbor in depth:
                    continue
                depth[neighbor] = depth[node] + 1
                entry_pred[neighbor] = entry_pred.get(node, pred)
                queue.append((neighbor, entry_pred[neighbor]))

        for terminal in all_terminals:
            if terminal in depth:
                reached_terminals.add(terminal)
                g_out.add((tag_of[source], entry_pred[terminal], tag_of[terminal]))
                n_edges += 1

    return g_out, len(all_sources), len(all_terminals), n_edges, len(all_terminals - reached_terminals)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reduce a merged HVAC topology graph to just source/terminal nodes with "
                    "readable tags and direct feeds/feedsAir edges (drops pumps/valves/HX/ductwork).")
    parser.add_argument("input", help="Merged Turtle file (Topology2BEM_2's output).")
    parser.add_argument("-o", "--output", default="terminal_source_topology.ttl",
                         help="Output Turtle file path.")
    parser.add_argument("--namespace", default="urn:OPS#", help="Instance namespace for the new tags.")
    args = parser.parse_args()

    g_in = Graph()
    g_in.parse(args.input, format="turtle")
    print("Loaded %d triples from %s" % (len(g_in), args.input))

    g_out, n_sources, n_terminals, n_edges, n_unreached = build(g_in, args.namespace)
    g_out.serialize(destination=args.output, format="turtle")
    print("Terminal/source topology written to %s (%d triples): %d source(s), %d terminal(s), "
          "%d direct feeds/feedsAir edge(s)" % (args.output, len(g_out), n_sources, n_terminals, n_edges))
    if n_unreached:
        print("%d/%d terminal(s) have no path to any source (dropped from the graph, not just unlinked)"
              % (n_unreached, n_terminals))


if __name__ == "__main__":
    main()
