# Baykar Internship Workspace

This repository is the working tree for internship deliverables and implementation work completed during the Baykar internship period.

The main active project in this workspace is:

- `projects/xdts`: X Documentation Tracing System (XDTS), a Python desktop application for document custody, transfer tracking, audit history, and admin operations

## Workspace Layout

```text
baykar-internship/
|-- projects/
|   `-- xdts/
|-- docs/
`-- README.md
```

- `projects/xdts` contains the source code, tests, deployment scripts, generated runtime folders, and project-specific documentation.
- `docs` is reserved for top-level workspace notes when needed.

## XDTS Quick Start

Run the GUI:

```powershell
python projects/xdts/main.py
```

Initialize the first admin:

```powershell
python projects/xdts/main.py --initialize-admin --username <admin_name>
```

Run the automated tests:

```powershell
python -m unittest discover -s projects/xdts/tests -v
```

## Where To Read First

- Project overview: `projects/xdts/README.md`
- Main GUI: `projects/xdts/gui.py`
- Business logic: `projects/xdts/services.py`
- Database layer: `projects/xdts/database.py`
- Tests: `projects/xdts/tests/`

## Notes

- This repository is organized as a working implementation repository, not a polished public portfolio.
- Generated project-local folders such as `data/`, `logs/`, `backups/`, `dist/`, and `.test-work/` live under `projects/xdts/`.
- Sensitive or proprietary company information should remain excluded from this workspace.
