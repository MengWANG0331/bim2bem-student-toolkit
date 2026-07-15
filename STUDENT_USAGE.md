# Student quick start

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
