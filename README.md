# BIM2BEM Student Toolkit

Turn an IFC building model (IFC4) into useful BEM (Building Energy Model)
data — no coding, no source-code reading required to just *use* it. This repo
is intended for teaching and student use: each student can fork the
repository, open it in GitHub Codespaces, upload an IFC file, and run the
conversion tools without installing anything locally.

This toolkit has **two independent routes**, covering two different parts of
a BIM2BEM workflow. Pick whichever matches what you need — they don't depend
on each other.

| Route | Input | Output | Covers |
|---|---|---|---|
| **BIM2BEM-GEOMETRY** | `.ifc` | `.gbxml` + `.idf` | Zone/space geometry, walls, floors, windows |
| **BIM2BEM-HVAC** | `.ifc` | knowledge graph (`.ttl`) + review `.csv`s | HVAC equipment, ductwork/piping connectivity, terminal-to-source tracing |

**New here? Start with [GUIDE.md](GUIDE.md) for a plain step-by-step walkthrough of both routes.**

---

## Route 1: BIM2BEM-GEOMETRY

```
your_model.ifc  --[this toolkit]-->  model.gbxml + model.idf
```

Runs the full IFC → cbip.xsd XML → gbXML → IDF chain (Java geometry
exporter + C++/CGAL space-boundary engine + OpenStudio SDK), packaged as a
single prebuilt Docker image — you never see or touch the source.

### For students: use GitHub Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/MengWANG0331/bim2bem-student-toolkit)

Recommended workflow for students:
1. Fork this repository to your own GitHub account.
2. Open the fork in GitHub Codespaces.
3. Upload an IFC file into [cases_in](cases_in), or use the built-in sample model.
4. Run the launcher script from the terminal (`./codespace_run.sh` uses the
   sample; `./codespace_run.sh cases_in/your_model.ifc` uses your own file).

This approach runs entirely in the browser and avoids local Docker setup.
See [GUIDE.md](GUIDE.md) for the exact steps.

### Run locally instead

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/),
installed and running.

**Windows**: drag your `.ifc` file onto [`run.bat`](run.bat) (or run
`run.bat path\to\model.ifc` from a terminal).

**Mac / Linux**:
```bash
chmod +x run.sh   # first time only
./run.sh path/to/model.ifc
```

The first run downloads the pipeline image (a few hundred MB); after that it's cached.

### Output

Results land in `cases_out/`:
- `<name>.gbxml` — intermediate gbXML 7.03 geometry
- `<name>.idf` — EnergyPlus input file, ready to open in OpenStudio/EnergyPlus
- `timing.json` — how long each of the 3 pipeline stages took

### What's happening under the hood

1. **IFC → cbip.xsd XML** — Java exporter reads the IFC4 model's spaces, walls, slabs, openings.
2. **cbip.xsd XML → gbXML** — CBIP (C++/CGAL) computes real space-boundary topology: which
   surfaces are exterior vs. interior/shared-between-spaces, then exports gbXML.
3. **gbXML → IDF** — converted to an EnergyPlus IDF via the OpenStudio SDK.

`docker/Dockerfile` and `docker/entrypoint.sh` are included so you can see exactly what the
container runs — but the Dockerfile is not buildable from this repo alone (the CBIP and Java
exporter source live in separate, unpublished repos). You always pull the prebuilt image.

### Known limitations

- No wall/roof construction or material-layer support yet — every surface uses generic
  properties, so absolute energy results (not just geometry) should be treated as
  provisional.
- Door vs. window type is not preserved — all openings currently export as generic
  `Window`-type fenestration surfaces.
- Very large models (100+ spaces) can be slow: the space-adjacency check is O(n²).
- No HVAC systems in the output IDF at all — see Route 2 for that side of the model.

---

## Route 2: BIM2BEM-HVAC (BIM2Graph)

```
your_model.ifc  --[this toolkit]-->  knowledge graph (.ttl) + review .csv files
```

Runs IFC → a [Brick](https://brickschema.org/) + [FSO](https://w3id.org/fso)
knowledge graph → a simplified, human-readable HVAC topology (which
radiators/diffusers/terminals are fed by which boilers/chillers, duct and
pipe runs collapsed away). Plain Python, **source code included** in
[`bim2graph/`](bim2graph/) — nothing hidden, nothing compiled.

**Scope, read this before you start:** this route currently stops at the
knowledge graph + topology views. It does **not** yet populate an
EnergyPlus IDF with HVAC objects — that next stage (knowledge graph → IDF)
is still in development and not part of this toolkit yet. Use this route to
extract and inspect your model's HVAC system topology, not to get a
simulation-ready file.

### No install? Use GitHub Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/MengWANG0331/bim2bem-student-toolkit?devcontainer_path=.devcontainer/bim2graph/devcontainer.json)

When creating the codespace, if you're not sent straight to this route, pick
the **bim2graph** dev container configuration from the dropdown.

### Run locally instead

Requires [Python 3.11+](https://www.python.org/downloads/) — no Docker needed for this route.

**Windows**: drag your `.ifc` file onto [`run_bim2graph.bat`](run_bim2graph.bat) (or run
`run_bim2graph.bat path\to\model.ifc` from a terminal).

**Mac / Linux**:
```bash
chmod +x run_bim2graph.sh   # first time only
./run_bim2graph.sh path/to/model.ifc
```

The first run creates a local Python environment and installs dependencies (a
couple of minutes); later runs reuse it.

### Output

Results land in `cases_out_bim2graph/`, all prefixed with your model's name:
- `_kg.ttl` — the raw knowledge graph (every IFC element classified into Brick/BOT/FSO)
- `_bridged.ttl` / `_merged.ttl` — intermediate graphs
- `_source_trace.csv` — which heat/cold source feeds each terminal (radiator, FCU, VAV, ...)
- `_terminal_source_topology.ttl` — simplified source→terminal graph with readable tags instead of GUIDs
- `_component_topology.ttl` — merged graph with duct/pipe runs collapsed into direct component-to-component edges
- `*_review.csv` files — flag anything the automatic classification/bridging wasn't fully confident about, worth a manual look

### Known limitations

- **Air-side source tracing not yet supported**: `_source_trace.csv` only recognizes
  Boiler/Chiller/Cooling_Tower as heat/cold sources. A pure ventilation system (AHU/fan-driven,
  no boiler/chiller) will report every terminal as "no source found" — this is a scope gap in
  the current source list, not a sign your model's ductwork is broken.
- **Equipment-type coverage for cooling/ventilation-side equipment (FCU, MVHR, AC units, pump
  subtypes) is unverified against real data** — the IFC→Brick mapping tables have entries for
  these, but no real-world test model exercising them has been available yet, unlike the
  heating/radiator and AHU/ventilation paths, which have been validated end-to-end.
- **Room/zone assignment is a manual step, by design**: terminal-to-source tracing is fully
  automatic (needs only equipment connectivity), but terminal-to-room assignment depends on
  IFC spatial-containment data that real-world exports frequently omit — treat the
  `zone_name_review.csv`-style checks as a manual curation step, not something the tool
  guarantees for you.
- No EnergyPlus IDF output yet (see Scope note above).

---

## If something goes wrong

| Message | Route | What to do |
|---|---|---|
| `Docker was not found` | Geometry | Docker Desktop isn't installed, or isn't on your PATH. Reinstall it, or switch to Codespaces. |
| `Docker pull failed` | Geometry | Docker Desktop isn't open/running, or no internet connection. |
| `Python was not found` | HVAC | Install Python 3.11+ and make sure it's on your PATH. |
| `File not found` | Both | Double-check the path/filename you passed matches your uploaded `.ifc` exactly. |
| Pipeline runs but errors partway through | Both | Copy the full text printed in the terminal and share it when asking for help — it tells us exactly which stage failed. |

If you hit an issue not covered here, open an issue on this repository with your terminal output attached.
