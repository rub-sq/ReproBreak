<p align="center">
  <img src="images/logo.png" alt="ReproBreak logo" height="360" />
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

```bash
python create_dataset.py
```

### Phase 2 — Verify reproducibility

Place a `Makefile` with `start`, `test`, `stop`, and `setup-e2e` targets under:

```text
data/reproduction_files/repos/<repo-name>/
```

Then run:

```bash
python create_reproducible_dataset.py
```

### Phase 3 — Save results

```bash
python save_reproduction.py
```

### Configuration

Key settings in `config.py`:

- `REPO_LIST`
- `START_WITH_CLEAN_DB`
- `PARALLEL_CONTAINERS`
- `DELETE_REPO_AFTER_ANALYZE`

</details>

---

## Citation

If you use ReproBreak in your research, please cite:

```bibtex
@inproceedings{reprobreak2026,
  title={ReproBreak: A Dataset of Reproducible Web Locator Breaks},
  author={...},
  booktitle={...},
  year={2026}
}
```

---

## License

MIT License
