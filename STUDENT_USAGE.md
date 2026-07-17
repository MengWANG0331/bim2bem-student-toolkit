# Student quick start

This toolkit has two independent routes (see [README.md](README.md)):
**BIM2BEM-GEOMETRY** (below) and **BIM2BEM-HVAC** (BIM2Graph, see the
section at the bottom of this file).

## Route 1: BIM2BEM-GEOMETRY

1. Fork this repository to your own GitHub account.
2. Open the fork in GitHub Codespaces.
3. Wait for the environment to finish loading.
4. Upload your IFC file into the cases_in folder, or simply use the sample model.
5. Run the conversion tool:

```bash
./codespace_run.sh
```

To process your own file, use:

```bash
./codespace_run.sh cases_in/your_model.ifc
```

6. Open the generated files in the cases_out folder.

If your IFC file has spaces in its name, quote the path:

```bash
./codespace_run.sh "cases_in/My Building.ifc"
```

## Route 2: BIM2BEM-HVAC (BIM2Graph)

1. Fork this repository to your own GitHub account (same fork as Route 1).
2. Open the fork in GitHub Codespaces, picking the **bim2graph** dev
   container configuration (or use this direct link:
   `https://codespaces.new/<your-fork>?devcontainer_path=.devcontainer/bim2graph/devcontainer.json`).
3. Upload your IFC file into the cases_in folder.
4. Run:

```bash
./codespace_run_bim2graph.sh cases_in/your_model.ifc
```

5. Open the generated files in the cases_out_bim2graph folder.

This route stops at a knowledge graph + HVAC topology views — it does not
produce an EnergyPlus IDF yet (see README.md's Route 2 known limitations).
