#!/bin/bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "usage: docker run -v <in>:/input -v <out>:/output IMAGE /input/<model>.ifc" >&2
    exit 1
fi

INPUT_IFC="$1"
NAME=$(basename "$INPUT_IFC" .ifc)
WORK="/tmp/work"
OUT="/output"
mkdir -p "$WORK" "$OUT"

# Copy the input into a writable work dir - IFCFileNameManager writes its
# output next to the input file, and /input may be a read-only mount.
LOCAL_IFC="$WORK/${NAME}.ifc"
cp "$INPUT_IFC" "$LOCAL_IFC"

CBIP_XML="$WORK/${NAME}_ifc_cbip.xml"
BST_XML="$WORK/${NAME}_ifc_bst.xml"
OBJ_FILE="$WORK/${NAME}.obj"
GBXML_FILE="$WORK/${NAME}.gbxml"
IDF_FILE="$WORK/${NAME}.idf"

TIMING="$OUT/timing.json"
echo "{" > "$TIMING"

echo "== stage 1/3: IFC -> cbip.xsd XML =="
SECONDS=0
java -cp "/opt/cbip-java/classes:/opt/cbip-java/dependency-jars/*" gr.tuc.cbip.ifc.test.CLIRunner "$LOCAL_IFC"
echo "  \"java_export_sec\": $SECONDS," >> "$TIMING"

echo "== stage 2/3: cbip.xsd XML -> gbXML (CBIP) =="
SECONDS=0
/opt/cbip/CBIP "$CBIP_XML" "$BST_XML" "$OBJ_FILE" "$GBXML_FILE"
echo "  \"cbip_sec\": $SECONDS," >> "$TIMING"

echo "== stage 3/3: gbXML -> IDF =="
SECONDS=0
/opt/venv/bin/python3 /opt/pipeline/gbxml_to_idf.py "$GBXML_FILE" "$IDF_FILE"
echo "  \"idf_conversion_sec\": $SECONDS" >> "$TIMING"

echo "}" >> "$TIMING"

cp "$GBXML_FILE" "$IDF_FILE" "$OUT/"
echo "done: outputs in /output ($(basename "$GBXML_FILE"), $(basename "$IDF_FILE"), timing.json)"
