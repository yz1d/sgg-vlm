# Schema Automator
Using a Python Package: `schema-automator` to help generate schema yaml files inferred from JSON data file.

The shcema automator POC for the example JSON file in the vedecom-data-pipeline repo, one can obstain the example schema by running
```bash
python schema_automator/generate_schema_from_json.py
```

One can view the resulting schema for the example JSON file, I also ran it for the Vedecom.json file, and it looks quite similar because they follow the same JSON structure. 

You can modify the output file path by appending flag `-o output/path/file.yaml`
