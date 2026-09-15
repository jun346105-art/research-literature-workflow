# Dependency Reproducibility

## S02 decision

This document records the packaging boundary verified in DR-S02. It changes dependency declarations and a packaging-contract test only; it does not change product imports, CLI routing, Docker configuration, models, validators, retrievers, or historical artifacts.

| Dependency | Final layer | Verified version | Evidence |
| --- | --- | --- | --- |
| NumPy | Default runtime | `2.5.2` in `requirements.runtime.lock`; `numpy>=2.5` in project metadata | `litflow.cli` imports `litflow.rag.dense` at module load, and `dense.py` / `windowed.py` import NumPy at module load. Runtime CLI help therefore needs NumPy. |
| LangGraph | Default runtime lock completion | `1.2.11` | Already declared in project metadata and imported by the Agent modules reached from the CLI top-level import chain. Docker installs the lock before installing the project with `--no-deps`, so the lock must contain it. |
| PyMuPDF | Test extra only | `1.28.2` as `.[test]` | Production PDF extraction imports `pypdf`, not PyMuPDF. `fitz` appears only in `tests/test_reading_context.py` to create fixture PDFs. Default CLI help, Offline Docker configuration, and the Reading Context production module do not import it. |
| jsonschema | Test/evaluation extra only | `4.25.0` in `requirements.test.lock` and `.[test]` | Retrieval Quality R1 metrics do not require it, but formal R1 package validation explicitly uses `Draft202012Validator`. It remains outside the default runtime. |

## Import graph and exclusion boundary

```text
litflow.cli -> agent.pilot -> agent.runtime -> langgraph
litflow.cli -> rag.dense -> numpy
rag.windowed -> numpy
reading_context -> pdf.extractor -> pypdf
tests/test_reading_context.py -> pytest.importorskip("fitz") -> PyMuPDF
retrieval_quality_r1.validate_json_schema_documents -> jsonschema.Draft202012Validator
rag.dense._Encoder -> torch + transformers (delayed, Dense-only)
```

Torch and Transformers remain outside the default runtime and test extra. They are imported only when Dense `_Encoder` is instantiated for a Dense cache/search path; default CLI help does not instantiate it, and S02 neither rebuilds Dense caches nor installs embedding models. A future optional Dense installation contract may define that stack separately.

The distribution package name is `PyMuPDF`; the current test-side compatibility import remains `fitz`. The package ecosystem signals that `fitz` is a legacy compatibility import. S02 deliberately does not migrate production or test imports because production does not use it and import migration is outside this packaging-only scope.

## Install and verification contracts

Runtime/CLI path (the same dependency file Docker installs before `pip install --no-deps .`):

```powershell
python -m pip install -r requirements.runtime.lock
python -m pip install --no-deps .
python -m pip check
python -c "import numpy"
python -m litflow.cli --help
```

Development/evaluation test path uses the test lock and pytest for test execution:

```powershell
python -m pip install -r requirements.test.lock
python -m pip install "pytest==9.1.1"
python -m pytest -q tests/test_models.py tests/test_reading_context.py tests/test_retrieval_quality_r1.py tests/test_docker_packaging.py
```

The fresh-environment commands are run in a system-temporary venv. Passing Reading Context and R1 Schema tests without skips is the test-extra contract; neither PyMuPDF nor jsonschema is added to the runtime lock because the production graph does not require them.
