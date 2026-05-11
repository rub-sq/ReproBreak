<p align="center">
  <img src="images/logo.png" alt="ReproBreak logo" width="650" />
</p>

---

ReproBreak is a dataset of reproducible web locator breaks collected from real-world repositories. The dataset enables research on test fragility, locator robustness, and automated test repair by providing reproducible breaks caused by locator breaks.

---

## Requirements

| Tool | Version |
|:---|:---|
| Python | 3.10+ |
| Git CLI | any |
| Docker | with Compose |
| uv *(recommended)* | latest |

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/rub-sq/ReproBreak
cd ReproBreak
```

### 2. Download the dataset

Download the pre-built database from the artifact repository:

> **[Download locator_break.db](<DATASET_LINK>)**

Unzip and place it in the `data/` folder:

```bash
unzip locator_break.zip -d data/
```

### 3. Install dependencies

Using `uv` (recommended):

```bash
uv sync
```

<details>
<summary>Using pip instead</summary>

```bash
pip install -e .
```

</details>

---

## Reproducing a Locator Break

Reproduce a locator break from the dataset using its identifier:

```bash
python reproduce.py --locator_id <ID> --mode <MODE>
```

| Mode | Behaviour |
|:---|:---|
| `reproduce_break` | Reverts the locator to its old value — test is expected to **fail** |
| `fixed` | Runs with the current locator — test is expected to **pass** |
| `original` | Runs tests without modifying the locator |

### Example

```bash
python reproduce.py --locator_id 42 --mode reproduce_break --db data/locator_break.db
```

### Expected Behaviour

```text
[FAIL] reproduce_break mode
[PASS] fixed mode
```

> Reproducing a locator break may require downloading Docker images and can take several minutes depending on repository size and internet connection.

---

## Project Structure

```text
reprobreak/
├── reproduce.py                     # Reproduce a locator break
├── create_dataset.py                # (Optional) Phase 1: Mine locator changes
├── create_reproducible_dataset.py   # (Optional) Phase 2: Verify reproducibility
├── save_reproduction.py             # (Optional) Phase 3: Store results in DB
├── config.py                        # Global configuration
├── database/
│   └── schema.sql                   # SQLite schema
└── data/
    ├── locator_break.db             # Dataset (download separately)
    └── reproduction_files/          # Per-repository reproduction environments
```

---

## Building the Dataset *(optional)*

<details>
<summary>Click to expand</summary>

The pre-built database covers 200+ repositories. To extend or rebuild the dataset from scratch:

### Phase 1 — Mine locator changes

In config.py set the following variables:
- `REPO_LIST`: List of repositories to mine (format: `owner/repo`)
- `START_WITH_CLEAN_DB`: Set to `True` to start with an empty database, or `False` to append to existing data.
- `DELETE_REPO_AFTER_ANALYZE`: Set to `True` to delete a repo after analyzing. Setting this to `False` may result in huge storage consumption.

Then run:

```bash
python create_dataset.py
```

This will clone all repositories iteratively and analyze their commit history to find locator changes. This creates a SQLite database at `output/<TIMESTAMP>/locator_break.db` (if `START_WITH_CLEAN_DB` is `False` at `output/locator_break.db`) containing mined locator changes and their metadata.

### Phase 2 — Verify reproducibility

For a repository, place the `Dockerfile` and the test runner script `/run_tests.sh` at `data/reproduction_files/repos/<repo-name>/`. 

Then run:

```bash
python create_reproducible_dataset.py <repo>
```

<style>
ol { list-style-type: decimal !important; }
</style>

This will clone the repository and iterate through all commits containing a locator change. For each commit, it will:
1. Try to build an image for the commit.
2. If the build succeeds, it will iterate through all test_files. For each test file, it will:
    1. Run a container for the commit image and execute `/run_tests.sh`, which then run all tests in the test file.
    2. If all tests pass, it will iterate through all locator changes in the test file. For each locator change, it will:
        1. Replace the locator in the codebase with its old value (before the change).
        2. Run a container for the commit image with the change mounted and execute `/run_tests.sh` again.
        3. If the test fails, it will mark the locator change as a reproducible break in the database. If it passes, the locator change is not break.

The results will be stored in a numbered folder under `data/reproduction_files/repos/<repo-name>/<run_number>/`. This folder will contain the following files:
- `results.json`: A JSON file containing information about the state of all inspected lcoator changes during this run.
- `Dockerfile`: The Dockerfile used to build the image for this run.
- `run_tests.sh`: The test runner script used to run tests for this run.

The results can be analyzed using a script.

To get a summary of the results for a specific run, use the following command:

```bash
python analyze_results.py <repo_name> <run_number>
```

To get a summary of the results for all runs in a project use the following command instead:

```bash
python analyze_results.py <repo_name> <run_number>
```

### Phase 3 — Save results

After one or multiple runs of phase 2, run the following command to save the results in the database:

```bash
python save_reproduction.py <repo>
```

This will read the results from each run for the repository in order and insert the files used for the reproduction, and its corresponding reproducible locator breaks into the database.

### Configuration

Key settings in `config.py`:

- `REPO_LIST`
- `START_WITH_CLEAN_DB`
- `STOP_ON_ERROR`
- `DELETE_REPO_AFTER_ANALYZE`

</details>
