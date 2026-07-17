"""Rewrites every URI in a Turtle graph that starts with one base namespace to
start with another, leaving everything else untouched. Fills a gap in the
existing pipeline: Topology2BEM_2 hardcodes its BLDG namespace as "urn:OPS#"
(so its input/output must be in that namespace), while Topology2BEM_4 expects
"http://example.com/OPS#" (its own hardcoded OPS namespace). A file literally
named "HVAC_topology_BEM_URL.ttl" is what Topology2BEM_4's __main__ reads,
implying this conversion step already existed in an undocumented/lost form -
this script is a generic, reusable replacement for it.
"""
import argparse

from rdflib import Graph, URIRef

DEFAULT_FROM_NAMESPACE = "urn:OPS#"
DEFAULT_TO_NAMESPACE = "http://example.com/OPS#"


def rename_namespace(g_in: Graph, from_ns: str, to_ns: str) -> Graph:
    g_out = Graph()
    for prefix, namespace in g_in.namespace_manager.namespaces():
        g_out.namespace_manager.bind(prefix, namespace)

    def remap(term):
        if isinstance(term, URIRef) and str(term).startswith(from_ns):
            return URIRef(to_ns + str(term)[len(from_ns):])
        return term

    for s, p, o in g_in:
        g_out.add((remap(s), remap(p), remap(o)))
    return g_out


def main() -> None:
    parser = argparse.ArgumentParser(description="Rewrite a Turtle graph's base namespace.")
    parser.add_argument("input", help="Input Turtle file.")
    parser.add_argument("-o", "--output", required=True, help="Output Turtle file path.")
    parser.add_argument("--from-namespace", default=DEFAULT_FROM_NAMESPACE,
                         help="Namespace prefix to replace (default matches Topology2BEM_2's BLDG namespace).")
    parser.add_argument("--to-namespace", default=DEFAULT_TO_NAMESPACE,
                         help="Replacement namespace prefix (default matches Topology2BEM_4's OPS namespace).")
    args = parser.parse_args()

    g_in = Graph()
    g_in.parse(args.input, format="turtle")
    g_out = rename_namespace(g_in, args.from_namespace, args.to_namespace)
    g_out.serialize(destination=args.output, format="turtle")
    print("Renamed %s -> %s across %d triples, written to %s"
          % (args.from_namespace, args.to_namespace, len(g_out), args.output))


if __name__ == "__main__":
    main()
