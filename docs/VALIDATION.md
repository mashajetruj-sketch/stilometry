# Validation

The project is offline-capable with no required third-party packages.

Use the optional `jsonschema` extra when the wheel is already available locally:

```powershell
python -m pip install --no-index --find-links .\wheels ".[schema]"
```

When `jsonschema` is installed, runtime validation uses
`Draft202012Validator(schema).iter_errors`. Without it, the built-in strict
Draft 2020-12-compatible fallback recursively validates object types,
required/properties, additional properties, arrays, and array items. Both paths
reject malformed nested values such as `sources: [1]`; neither downloads a
dependency at runtime.

Run the complete local gate:

```powershell
pip install -e .
python stilometry.py install-models
python -m pytest -q
python scripts\validate_install.py
python -m compileall -q src scripts stilometry.py
```

The selected backend is available through
`stilometry.schemas.validation_backend()`.
