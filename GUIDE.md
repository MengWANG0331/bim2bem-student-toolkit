# How to use this toolkit

This toolkit has **two independent routes** — pick the one that matches what
you need (see [README.md](README.md) for the overview table):

- **Route 1: BIM2BEM-GEOMETRY** (folder: [`bim2bem-geometry/`](bim2bem-geometry/)) —
  IFC → gbXML → EnergyPlus IDF (zone geometry, walls, windows). Docker-based.
- **Route 2: BIM2BEM-HVAC** (folder: [`bim2bem-hvac/`](bim2bem-hvac/), BIM2Graph) —
  IFC → knowledge graph → HVAC system topology. Plain Python, no Docker.

Each route has its own local option, its own GitHub Codespaces option, and
its own `cases_in/`/`cases_out/` subfolders. This repository is designed so
each student can use it from their own GitHub account — for Codespaces, fork
the repository first, then open your fork in Codespaces (see each route's
Option A below).

---

## Route 1: BIM2BEM-GEOMETRY

### Option A: GitHub Codespaces (recommended, nothing to install)

You need a free GitHub account (github.com) — nothing else.

**Step 1: Open a Codespace**

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/MengWANG0331/bim2bem-student-toolkit)

If you are a student, first fork this repository to your own GitHub account.
Then open your fork in Codespaces from the green **Code** button →
**Codespaces** tab → **Create codespace on main**.

The first time, this can take **5-10 minutes** to finish setting up — it's
downloading the same pipeline image as the Docker option (a few hundred MB),
just running it in the cloud instead of on your computer. If the progress bar
or "Setting up remote connection" message seems stuck, that's normal — just
wait, don't close the tab.

**Step 2: Add your IFC file**

In the file explorer on the left side of the browser window, open the
`bim2bem-geometry` folder, right-click the `cases_in` folder inside it and
choose **Upload...**, then pick your `.ifc` file. (Dragging the file onto
the folder also works.)

**If your file name has spaces in it** (e.g. `My Building.ifc`), either
rename it first (e.g. `my_building.ifc`) or wrap the path in quotes in the
next step — otherwise the terminal will read it as two separate arguments.

**Step 3: Run it**

Open a terminal (menu **Terminal → New Terminal**, or `` Ctrl+` ``) and run:

```bash
cd bim2bem-geometry
./codespace_run.sh
```

This uses the sample IFC file included in `cases_in`.

To process your own IFC file, run:

```bash
./codespace_run.sh cases_in/your_model.ifc
```

(File name has spaces? Quote the path: `./codespace_run.sh "cases_in/My Building.ifc"`)

**Step 4: Download your results**

In the file explorer, open `bim2bem-geometry/cases_out`, right-click each
file, and choose **Download**.

**When you're done**

Free GitHub accounts get about 60 hours/month of Codespaces — plenty for this
toolkit. Codespaces pause automatically after ~30 minutes idle, but to be
safe: go to **github.com/codespaces**, find this one, and click **Stop** (or
**Delete** if you're finished with it for good).

### Option B: Docker Desktop (run on your own computer)

**Step 1: Install Docker Desktop (one time only)**

1. Download it from **https://www.docker.com/products/docker-desktop/**
2. Install it like any normal application.
3. Open Docker Desktop once and leave it running in the background. You'll
   know it's ready when you see the whale icon in your system tray (Windows)
   or menu bar (Mac).

You don't need a Docker account and you don't need to learn Docker — this
toolkit hides all of that for you.

**Step 2: Get this toolkit**

Download or clone this repository to your computer.

**Step 3: Run it on your IFC file**

Windows: drag your `.ifc` file and drop it directly onto
`bim2bem-geometry\run.bat`. A black terminal window will open and show
progress. (Alternative: `bim2bem-geometry\run.bat path\to\your_model.ifc`
from a terminal.)

Mac / Linux:
```bash
cd bim2bem-geometry
chmod +x run.sh          # first time only
./run.sh path/to/your_model.ifc
```

**The first run will take a few extra minutes** — it needs to download the
pipeline image (a few hundred MB) once. Every run after that is fast, since
the image is cached on your computer.

### What you get

Look in `bim2bem-geometry/cases_out/` for:

| File | What it is |
|---|---|
| `<your_model>.gbxml` | Intermediate geometry file (gbXML format) |
| `<your_model>.idf`   | The EnergyPlus model — open this in OpenStudio or EnergyPlus |
| `timing.json`        | How long each pipeline step took |

You can now open the `.idf` file in **OpenStudio** or **EnergyPlus** to run
an energy simulation (envelope/geometry only — no HVAC, no material layers
yet, see README's known limitations).

---

## Route 2: BIM2BEM-HVAC (BIM2Graph)

**Before you start**: this route extracts and simplifies your model's HVAC
system topology (equipment, connectivity, which terminals trace back to
which sources) into inspectable graph/CSV files. It does **not** produce a
simulation-ready IDF yet — that's a separate, still-in-development stage not
included in this toolkit. Use this route to understand/QA your model's HVAC
data, not to get a final EnergyPlus file.

### Option A: GitHub Codespaces (recommended, nothing to install)

**Step 1: Open a Codespace on the BIM2Graph configuration**

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/MengWANG0331/bim2bem-student-toolkit?devcontainer_path=.devcontainer/bim2graph/devcontainer.json)

Click the button above. If GitHub shows you a configuration picker instead
of jumping straight in, choose **bim2graph**. Setup is quick here (plain
Python, no large image to download) — usually under a minute.

**Step 2: Add your IFC file**

In the file explorer, open the `bim2bem-hvac` folder, right-click the
`cases_in` folder inside it → **Upload...**.

**Step 3: Run it**

```bash
cd bim2bem-hvac
./codespace_run_bim2graph.sh cases_in/your_model.ifc
```

**Step 4: Download your results**

Open `bim2bem-hvac/cases_out`, right-click each file, **Download**.

### Option B: Run locally (Python, no Docker)

**Step 1: Install Python (one time only)**

Download Python 3.11+ from **https://www.python.org/downloads/**. During
install, check **"Add python.exe to PATH"** (Windows).

**Step 2: Get this toolkit**

Download or clone this repository to your computer.

**Step 3: Run it on your IFC file**

Windows: drag your `.ifc` file onto `bim2bem-hvac\run_bim2graph.bat`.

Mac / Linux:
```bash
cd bim2bem-hvac
chmod +x run_bim2graph.sh   # first time only
./run_bim2graph.sh path/to/your_model.ifc
```

**The first run sets up a local Python environment** (a couple of minutes);
later runs reuse it and are fast.

### What you get

Look in `bim2bem-hvac/cases_out/` (see README.md's Route 2 section for the
full file list and what each one means) — the most useful starting points
are `_source_trace.csv` (which source feeds each terminal) and
`_terminal_source_topology.ttl` (a simplified source→terminal graph with
readable names instead of GUIDs).

Because the source code is plain, visible Python
(`bim2bem-hvac/bim2graph/` in this repo), you can also read exactly what
each stage does, or run individual stages yourself instead of the full
chain — see the comments at the top of each script.

---

## If something goes wrong

| Message | Route | What to do |
|---|---|---|
| `Docker was not found` | Geometry | Docker Desktop isn't installed, or isn't on your PATH. Reinstall it, or switch to Codespaces. |
| `Docker pull failed` | Geometry | Docker Desktop isn't open/running, or you have no internet connection. |
| `Python was not found` | HVAC | Install Python 3.11+ and make sure it's on your PATH (Windows: re-run the installer and check "Add to PATH"). |
| `File not found` in Codespaces | Both | Double-check you `cd`'d into the right route folder, uploaded the `.ifc` file into `cases_in/` first, and that the path after the run command matches its exact name. |
| Pipeline runs but errors partway through | Both | Copy the full text printed in the terminal and share it when asking for help — it tells us exactly which stage failed. |

## Good to know before you rely on the results

Both routes have known limitations — see the "Known limitations" section
under each route in `README.md` before treating results as final.

If you hit an issue not covered here, open an issue on this repository with
your terminal output attached.
