"""Traces every terminal unit in a merged Graph2BEM topology (Topology2BEM_2's
output) back to the real heat/cold source(s) that ultimately feed it, by
following brick:feeds/brick:feedsAir edges from each Boiler/Chiller/Cooling_Tower
node. Unlike terminal->room assignment (which depends on IFC spatial-containment
data that real exports frequently omit - see project memory), this only needs
the port-connectivity graph, which is present whenever the source IFC models
its distribution system at all. So this can run fully automatically, with no
manual-review step, as long as the direction of brick:feeds/feedsAir is correct
(this depends on the IFC_to_KG.py flow-direction fix of 2026-07-17 - a build on
an unfixed graph will silently produce the reverse of "who feeds whom").

Meant to feed simulation_HVACTemplate's plant/loop generation (Graph2BEM's
Passive2Active.py), which currently ignores the graph and unconditionally
emits one hardcoded chilled-water loop + one hot-water loop + one chiller +
one boiler regardless of the real topology.
"""
import argparse
from collections import defaultdict, deque

import pandas as pd
from rdflib import RDF, Graph, Namespace, URIRef

BRICK = Namespace("https://brickschema.org/schema/Brick#")

# Heat/cold-source equipment classes to trace from. Extend as new source
# types show up in real data (e.g. Domestic_Hot_Water heaters, heat pumps).
SOURCE_CLASSES = {"Boiler", "Chiller", "Cooling_Tower"}

# Terminal-facing classes worth reporting a source for - the room-serving
# virtual nodes Topology2BEM_2 creates (Radiator/FCU/VAV/CAV/DH/AC), plus the
# raw Brick classes a terminal might still carry if no merge applied to it
# (e.g. Space_Heater when merge_RAD found no brick:Room to attach it to -
# see the 2026-07-17 spatial-containment gap finding).
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


def build_adjacency(g: Graph) -> dict:
    adjacency = defaultdict(set)
    for pred in FEEDS_PREDICATES:
        for s, _, o in g.triples((None, pred, None)):
            adjacency[s].add(o)
    return adjacency


def trace(g: Graph):
    types = load_types(g)
    adjacency = build_adjacency(g)

    sources = [n for n, t in types.items() if t & SOURCE_CLASSES]
    all_terminals = {n for n, t in types.items() if t & TERMINAL_CLASSES}

    trace_rows = []
    reached_terminals = set()
    for source in sources:
        source_type = next(iter(types[source] & SOURCE_CLASSES))
        # BFS for shortest hop-count from this source to every reachable node.
        depth = {source: 0}
        queue = deque([source])
        while queue:
            node = queue.popleft()
            for neighbor in adjacency.get(node, ()):
                if neighbor not in depth:
                    depth[neighbor] = depth[node] + 1
                    queue.append(neighbor)

        for terminal in all_terminals:
            if terminal in depth:
                reached_terminals.add(terminal)
                terminal_type = next(iter(types[terminal] & TERMINAL_CLASSES))
                trace_rows.append({
                    "Terminal": str(terminal), "TerminalType": terminal_type,
                    "Source": str(source), "SourceType": source_type,
                    "Hops": depth[terminal],
                })

    unreached_rows = [
        {"Terminal": str(t), "TerminalType": next(iter(types[t] & TERMINAL_CLASSES))}
        for t in sorted(all_terminals - reached_terminals, key=str)
    ]

    return trace_rows, unreached_rows, len(sources), len(all_terminals)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trace each terminal unit in a merged HVAC topology graph back to "
                    "the heat/cold source(s) that feed it (Boiler/Chiller/Cooling_Tower).")
    parser.add_argument("input", help="Merged Turtle file (Topology2BEM_2's output).")
    parser.add_argument("-o", "--output", default="source_trace.csv",
                         help="Path for the terminal->source trace CSV.")
    parser.add_argument("--unreached-csv", default="source_trace_unreached.csv",
                         help="Path for terminals with no path back to any recognized source.")
    args = parser.parse_args()

    g = Graph()
    g.parse(args.input, format="turtle")
    print("Loaded %d triples from %s" % (len(g), args.input))

    trace_rows, unreached_rows, n_sources, n_terminals = trace(g)

    if trace_rows:
        df = pd.DataFrame(trace_rows).sort_values(["Terminal", "Hops"])
        df.to_csv(args.output, index=False)
    print("Found %d source(s) (Boiler/Chiller/Cooling_Tower), %d terminal(s). "
          "%d terminal-source link(s) written to %s"
          % (n_sources, n_terminals, len(trace_rows), args.output))

    if unreached_rows:
        pd.DataFrame(unreached_rows).to_csv(args.unreached_csv, index=False)
        print("%d/%d terminal(s) have NO path back to any recognized source - written to %s "
              "(check for a missing brick:feeds/feedsAir edge or an unmodeled source)"
              % (len(unreached_rows), n_terminals, args.unreached_csv))
    else:
        print("Every terminal traces back to at least one recognized source.")


if __name__ == "__main__":
    main()
