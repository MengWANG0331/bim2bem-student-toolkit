"""Chains all BIM2Graph stages on one IFC file: IFC -> knowledge graph ->
bridged Brick topology -> merged topology -> simplified views.

Usage: python run_pipeline.py path/to/model.ifc -o output_dir/
"""
import argparse
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def run(*args):
    print(f"== {' '.join(args)} ==")
    subprocess.run([sys.executable, *args], check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ifc_path")
    parser.add_argument("-o", "--output-dir", default="cases_out_bim2graph")
    args = parser.parse_args()

    name = os.path.splitext(os.path.basename(args.ifc_path))[0]
    out = args.output_dir
    os.makedirs(out, exist_ok=True)

    kg = os.path.join(out, f"{name}_kg.ttl")
    bridged = os.path.join(out, f"{name}_bridged.ttl")
    merged = os.path.join(out, f"{name}_merged.ttl")

    run(os.path.join(HERE, "00_ifc_to_kg", "IFC_to_KG.py"), args.ifc_path, "-o", kg,
        "--review-csv", os.path.join(out, f"{name}_classification_review.csv"),
        "--connectivity-review-csv", os.path.join(out, f"{name}_connectivity_review.csv"))

    run(os.path.join(HERE, "01_bridge_fso_to_brick.py"), kg, "-o", bridged,
        "--review-csv", os.path.join(out, f"{name}_bridge_review.csv"),
        "--zone-name-review-csv", os.path.join(out, f"{name}_zone_name_review.csv"))

    run(os.path.join(HERE, "02_merge_topology.py"), bridged, "-o", merged)

    run(os.path.join(HERE, "02b_source_trace.py"), merged,
        "-o", os.path.join(out, f"{name}_source_trace.csv"),
        "--unreached-csv", os.path.join(out, f"{name}_source_trace_unreached.csv"))
    run(os.path.join(HERE, "02c_collapse_connectors.py"), merged,
        "-o", os.path.join(out, f"{name}_component_topology.ttl"))
    run(os.path.join(HERE, "02d_terminal_source_topology.py"), merged,
        "-o", os.path.join(out, f"{name}_terminal_source_topology.ttl"))

    run(os.path.join(HERE, "01c_topology_audit.py"), kg,
        "--out-prefix", os.path.join(out, f"{name}_audit"))

    print(f"done: outputs in {out}")


if __name__ == "__main__":
    main()
