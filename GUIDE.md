# How to use this toolkit

Turn your IFC building model into an EnergyPlus IDF file. No coding required.

There are two ways to run this:

- **Option A: GitHub Codespaces (recommended)** — nothing to install, runs in
  your browser. Use this if installing Docker Desktop is giving you trouble.
- **Option B: Docker Desktop** — runs on your own computer, useful if you'll
  process many files and want to work offline.

## Option A: GitHub Codespaces (no install)

You need a free GitHub account (github.com) — nothing else.

### Step 1: Open a Codespace

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/MengWANG0331/bim2bem-student-toolkit)

Click the button above, or go to the repository page → the green **Code**
button → **Codespaces** tab → **Create codespace on main**.

The first time, this can take **5-10 minutes** to finish setting up — it's
downloading the same pipeline image as the Docker option (a few hundred MB),
just running it in the cloud instead of on your computer. If the progress bar
or "Setting up remote connection" message seems stuck, that's normal — just
wait, don't close the tab.

### Step 2: Add your IFC file

In the file explorer on the left side of the browser window, right-click the
`cases_in` folder and choose **Upload...**, then pick your `.ifc` file.
(Dragging the file onto the folder also works.)

**If your file name has spaces in it** (e.g. `My Building.ifc`), either
rename it first (e.g. `my_building.ifc`) or wrap the path in quotes in the
next step — otherwise the terminal will read it as two separate arguments.

### Step 3: Run it

Open a terminal (menu **Terminal → New Terminal**, or `` Ctrl+` ``) and run:

```bash
./codespace_run.sh cases_in/your_model.ifc
```

(File name has spaces? Quote the path: `./codespace_run.sh "cases_in/My Building.ifc"`)

### Step 4: Download your results

In the file explorer, open the `cases_out` folder, right-click each file, and
choose **Download**.

### When you're done

Free GitHub accounts get about 60 hours/month of Codespaces — plenty for this
toolkit. Codespaces pause automatically after ~30 minutes idle, but to be
safe: go to **github.com/codespaces**, find this one, and click **Stop** (or
**Delete** if you're finished with it for good).

## Option B: Docker Desktop (run on your own computer)

### Step 1: Install Docker Desktop (one time only)

1. Download it from **https://www.docker.com/products/docker-desktop/**
2. Install it like any normal application.
3. Open Docker Desktop once and leave it running in the background. You'll
   know it's ready when you see the whale icon in your system tray (Windows)
   or menu bar (Mac).

You don't need a Docker account and you don't need to learn Docker — this
toolkit hides all of that for you.

### Step 2: Get this toolkit

Download or clone this repository to your computer. You should end up with a
folder that looks like this:

```
bim2bem-student-toolkit/
  run.bat          <- Windows: use this one
  run.sh           <- Mac / Linux: use this one
  cases_in/
  cases_out/       <- your results will appear here
  README.md
  GUIDE.md          <- this file
```

### Step 3: Run it on your IFC file

**Windows**

Drag your `.ifc` file and drop it directly onto `run.bat`. That's it. A
black terminal window will open and show progress.

(Alternative: open a terminal in this folder and run
`run.bat path\to\your_model.ifc`.)

**Mac / Linux**

Open a terminal in this folder and run:

```bash
chmod +x run.sh          # first time only
./run.sh path/to/your_model.ifc
```

**The first run will take a few extra minutes** — it needs to download the
pipeline image (a few hundred MB) once. Every run after that is fast, since
the image is cached on your computer.

## What you get

When it finishes, look in the `cases_out/` folder for:

| File | What it is |
|---|---|
| `<your_model>.gbxml` | Intermediate geometry file (gbXML format) |
| `<your_model>.idf`   | The EnergyPlus model — open this in OpenStudio or EnergyPlus |
| `timing.json`        | How long each pipeline step took |

You can now open the `.idf` file in **OpenStudio** or **EnergyPlus** to run
an energy simulation.

## If something goes wrong

| Message | What to do |
|---|---|
| `Docker was not found` | (Option B) Docker Desktop isn't installed, or isn't on your PATH. Reinstall it and make sure the installer finishes without errors — or switch to Option A (Codespaces) instead. |
| `Docker pull failed` | (Option B) Docker Desktop isn't open/running, or you have no internet connection. Open Docker Desktop and check the whale icon, then try again. |
| `File not found` in Codespaces | (Option A) Double-check you uploaded the `.ifc` file into `cases_in/` first, and that the path after `codespace_run.sh` matches its exact name. |
| Pipeline runs but errors partway through | Copy the full text printed in the terminal and share it when asking for help — it tells us exactly which of the 3 stages failed. |

## Good to know before you rely on the results

This toolkit currently has a few known limitations (see `README.md` for
full detail):

- Every wall/roof/floor uses the same generic construction — there's no
  real material/insulation data yet, so treat absolute energy numbers as
  provisional; geometry (zone shapes, areas, adjacency) is the reliable part.
- Doors and windows both get exported as generic "Window" openings — the
  door/window distinction is not preserved yet.
- Very large models (100+ spaces) can take a long time to process.

If you hit an issue not covered here, open an issue on this repository with
your terminal output attached.
