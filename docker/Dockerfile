# Build context MUST be the DigiBUILD workspace root, e.g.:
#   docker build -f bim2bem-pipeline/docker/Dockerfile -t bim2bem-cbip:latest .
# (run from D:\OneDrive\Coding\Python_C\DigiBUILD)
#
# This Dockerfile only READS the sibling source folders via COPY. It never
# runs git in them and never writes anything back to them.
#
# NOTE for students: this file is included for transparency only. It is not
# buildable from this repo alone - stage 1/2 COPY from sibling source repos
# (the CBIP C++/CGAL engine and its Java IFC exporter) that are not published
# here. Pull the prebuilt image instead: see README.md.

# All 3 stages must share the same glibc (Debian 13 "trixie") so the CBIP
# binary built in cbip-build runs correctly when copied into runtime -
# mixing e.g. ubuntu:26.04 (newer glibc) as a build stage with a
# python:3.11-slim (trixie) runtime caused "GLIBC_2.43 not found" at runtime.
ARG DEBIAN_TAG=trixie-slim

# ---------------------------------------------------------------------------
# Stage 1: build the CBIP C++/CGAL executable
# ---------------------------------------------------------------------------
FROM debian:${DEBIAN_TAG} AS cbip-build

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential cmake default-jdk libboost-all-dev libeigen3-dev \
    libgmp-dev libmpfr-dev \
    wget xz-utils \
    && rm -rf /var/lib/apt/lists/*

RUN wget -q https://github.com/CGAL/cgal/releases/download/v6.0.1/CGAL-6.0.1.tar.xz -O /tmp/cgal.tar.xz \
    && mkdir -p /opt/CGAL-6.0.1 \
    && tar -xJf /tmp/cgal.tar.xz -C /opt/CGAL-6.0.1 --strip-components=1 \
    && rm /tmp/cgal.tar.xz

COPY common-boundary-intersection-projection-tool/ /src/cbip-cpp/

RUN mkdir -p /src/cbip-cpp/build \
    && cd /src/cbip-cpp/build \
    && cmake -DCGAL_DIR=/opt/CGAL-6.0.1 .. \
    && make CBIP -j"$(nproc)"

# ---------------------------------------------------------------------------
# Stage 2: build the Java IFC exporter (bim-library -> cbip-api -> cbip-ifc-in-house)
# ---------------------------------------------------------------------------
FROM debian:${DEBIAN_TAG} AS java-build

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    default-jdk maven \
    && rm -rf /var/lib/apt/lists/*

COPY bim-library/bim-library/ /src/bim-library/
COPY cbip-api/cbip-api/ /src/cbip-api/
COPY cbip-geometry-exporter/cbip-ifc-in-house/ /src/cbip-ifc-in-house/

RUN cd /src/bim-library && mvn -q -B install -DskipTests
RUN cd /src/cbip-api && mvn -q -B install -DskipTests
RUN cd /src/cbip-ifc-in-house && mvn -q -B install -DskipTests \
    && mvn -q -B dependency:copy-dependencies -DoutputDirectory=target/dependency-jars

# ---------------------------------------------------------------------------
# Stage 3: runtime image - only the compiled artifacts, no source
# ---------------------------------------------------------------------------
# Pinned to Python 3.11: OpenStudio 3.11.0's compiled SWIG bindings are not
# ABI-compatible with newer CPython (confirmed segfault in openstudiogbxml.so
# under Python 3.14, which ubuntu:26.04's python3 package defaults to).
FROM python:3.11-slim AS runtime

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    default-jre libboost-all-dev libgmp10 libmpfr6 \
    && rm -rf /var/lib/apt/lists/*

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir openstudio==3.11.0

COPY --from=cbip-build /src/cbip-cpp/build/CBIP /opt/cbip/CBIP
COPY --from=java-build /src/cbip-ifc-in-house/target/classes /opt/cbip-java/classes
COPY --from=java-build /src/cbip-ifc-in-house/target/dependency-jars /opt/cbip-java/dependency-jars

COPY bim2bem-pipeline/gbxml_to_idf.py /opt/pipeline/gbxml_to_idf.py
COPY bim2bem-pipeline/docker/entrypoint.sh /opt/pipeline/entrypoint.sh
RUN chmod +x /opt/pipeline/entrypoint.sh /opt/cbip/CBIP

ENTRYPOINT ["/opt/pipeline/entrypoint.sh"]
