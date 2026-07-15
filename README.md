# BIM2BEM Student Toolkit

Convert an IFC building model (IFC4) into an EnergyPlus IDF file. This repo is
intended for teaching and student use: each student can fork the repository,
open it in GitHub Codespaces, upload an IFC file, and run the conversion tools
without installing Docker locally.

**New here? Start with [GUIDE.md](GUIDE.md) for a plain step-by-step walkthrough.**

```
your_model.ifc  --[this toolkit]-->  model.gbxml + model.idf
```

## For students: use GitHub Codespaces

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/MengWANG0331/bim2bem-student-toolkit)

Recommended workflow for students:
1. Fork this repository to your own GitHub account.
2. Open the fork in GitHub Codespaces.
3. Upload an IFC file into [cases_in](cases_in), or use the built-in sample model.
4. Run the launcher script from the terminal.

The simplest start is:
```bash
./codespace_run.sh
```

This approach runs entirely in the browser and avoids local Docker setup.
See [GUIDE.md](GUIDE.md) for the exact steps.

## Requirements (for running locally instead)

- [Docker Desktop](https://www.docker.com/products/docker-desktop/), installed and running.
  (Windows/Mac: just install and open it once. No Docker knowledge needed beyond that.)

## Quickstart

**Windows**
1. Put your `.ifc` file anywhere.
2. Drag the `.ifc` file onto [`run.bat`](run.bat) (or run `run.bat path\to\model.ifc` from a terminal).

**Mac / Linux**
```bash
chmod +x run.sh   # first time only
./run.sh path/to/model.ifc
```

The first run downloads the pipeline image (a few hundred MB); after that it's cached.

## Output

Results land in `cases_out/` next to the scripts:
- `<name>.gbxml` — intermediate gbXML 7.03 geometry
- `<name>.idf` — EnergyPlus input file, ready to open in OpenStudio/EnergyPlus
- `timing.json` — how long each of the 3 pipeline stages took

## What's happening under the hood

1. **IFC → cbip.xsd XML** — Java exporter reads the IFC4 model's spaces, walls, slabs, openings.
2. **cbip.xsd XML → gbXML** — CBIP (C++/CGAL) computes real space-boundary topology: which
   surfaces are exterior vs. interior/shared-between-spaces, then exports gbXML.
3. **gbXML → IDF** — converted to an EnergyPlus IDF via the OpenStudio SDK.

`docker/Dockerfile` and `docker/entrypoint.sh` are included so you can see exactly what the
container runs — but the Dockerfile is not buildable from this repo alone (the CBIP and Java
exporter source live in separate, unpublished repos). You always pull the prebuilt image.

## Known limitations

- No wall/roof construction or material-layer support yet — every surface uses generic
  properties, so absolute energy results (not just geometry) should be treated as
  provisional.
- Door vs. window type is not preserved — all openings currently export as generic
  `Window`-type fenestration surfaces.
- Very large models (100+ spaces) can be slow: the space-adjacency check is O(n²).

## Troubleshooting

- `Docker was not found` — install Docker Desktop and make sure it's running (check for
  the whale icon in your system tray/menu bar).
- `Docker pull failed` — check your internet connection; the image is public, no login needed.
- Pipeline errors are printed to the console — if a run fails, copy the full output when
  asking for help.
