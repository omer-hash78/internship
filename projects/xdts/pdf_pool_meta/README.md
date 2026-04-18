# XDTS PDF Test Pool

This directory stores the metadata contract for the XDTS sample PDF pool.

The current XDTS runtime does not ingest or link binary PDFs. The PDF payloads
live in `../pdf_pool/` and this metadata folder defines how that pool is named,
inventoried, and validated.

All planned sample PDFs must live directly in `../pdf_pool/`. Do not place the
PDF pool files in nested subfolders.

## Required Filename Format

Every sample PDF in `../pdf_pool/` must follow exactly:

```text
XX_XX_XXX_XX_XXXX_Document_Title_R000_YYYY_MM_DD.pdf
```

Rules:

- code segments are uppercase
- code segment lengths are exactly `2 / 2 / 3 / 2 / 4`
- document title uses underscore-separated English-style words
- spaces are not allowed anywhere in the filename
- revision is always `R` + 3 digits
- date is always `YYYY_MM_DD`

Suggested validation regex for future tooling:

```text
^[A-Z]{2}_[A-Z]{2}_[A-Z]{3}_[A-Z]{2}_[0-9]{4}_[A-Za-z0-9]+(?:_[A-Za-z0-9]+)*_R[0-9]{3}_[0-9]{4}_[0-9]{2}_[0-9]{2}\.pdf$
```

## Code Legend

Department codes:

- `AV`: avionics / flight operations
- `MT`: maintenance
- `SA`: safety
- `QA`: quality assurance

System codes:

- `FL`: flight
- `EN`: engine
- `EL`: electrical / avionics electronics
- `HY`: hydraulic
- `LG`: landing gear

Document type codes:

- `CL`: checklist
- `PR`: procedure
- `RP`: report
- `PL`: parts list
- `DG`: diagram guide

Subsystem codes used in this pool are free-form but fixed per document family:

- `NAV`, `FUE`, `INS`, `PWR`, `ACT`, `LND`, `TMP`, `COM`

## Planned Document Set

Revision family 1:

- `AV_FL_NAV_CL_1001_Preflight_Checklist_R000_2026_04_10.pdf`
- `AV_FL_NAV_CL_1001_Preflight_Checklist_R001_2026_04_14.pdf`
- `AV_FL_NAV_CL_1001_Preflight_Checklist_R002_2026_04_17.pdf`

Revision family 2:

- `MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R000_2026_04_09.pdf`
- `MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R001_2026_04_13.pdf`
- `MT_EN_FUE_PR_1002_Engine_Maintenance_Procedure_R002_2026_04_16.pdf`

Single-revision documents:

- `SA_FL_INS_RP_1003_Safety_Inspection_Report_R000_2026_04_11.pdf`
- `QA_EL_PWR_PL_1004_Avionics_Parts_List_R000_2026_04_08.pdf`
- `MT_HY_ACT_CL_1005_Hydraulic_System_Checklist_R000_2026_04_12.pdf`
- `AV_LG_LND_DG_1006_Landing_Gear_Diagram_Guide_R000_2026_04_07.pdf`
- `SA_EN_TMP_RP_1007_Engine_Temperature_Log_R000_2026_04_15.pdf`
- `QA_FL_COM_PR_1008_Cockpit_Communication_Test_Procedure_R000_2026_04_18.pdf`

## Required PDF Content Rules

Each PDF must be a digital text PDF, not a screenshot-only or scan-like page.

Each PDF must contain:

- visible document title
- visible document code
- visible revision number
- visible effective or update date
- short summary or abstract
- at least 2 body paragraphs
- at least 1 table with 3 or more rows
- at least 1 embedded image or simple technical diagram with caption

Recommended page structure:

- top header block with code, title, revision, and date
- summary paragraph
- body section(s)
- table
- image or diagram near the lower half of page 1 or on page 2

Language mix for this pool:

- filenames remain English-style for consistency
- `1001`, `1003`, `1005`, `1007` are English-dominant
- `1002`, `1004`, `1006`, `1008` are Turkish-dominant
- Turkish-dominant PDFs should still include the exact English filename title on page 1

## Revision Rules

For revision families, each new revision must change actual content, not only the
filename and date.

Minimum delta per revision:

- update at least one paragraph or procedural note
- change at least one table row, value, or checklist item
- add or adjust a revision note on page 1

Keep the same code block and title across a revision family. Only the revision and
date should change in the filename.

## Inventory Contract

`index.csv` is the authoritative machine-readable inventory for future import and
selection tooling.

Required columns:

```text
filename,document_family,revision,document_date,language,department_code,system_code,subsystem_code,doc_type_code,serial,title,previous_revision_filename,has_table,has_image
```

## Validation

Validate the inventory and the PDF pool:

```powershell
python projects/xdts/tools/validate_pdf_pool.py --manifest-only
python projects/xdts/tools/validate_pdf_pool.py
```
