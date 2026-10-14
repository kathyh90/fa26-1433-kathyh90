# Raw data

Store original, unmodified source data here. These files are ignored by Git by default. Document each source, access date, and any instructions needed to obtain the data.

Public files are downloaded by `code/00_download_raw_data.py`; their sources are documented in `code/sources.py` and each download is logged in `download_manifest.csv`.

## Data not publicly available

State aid and alternative-application data by high school, searched 2026-10-09. These need a data request.

| State | Data | Status | Ask |
|---|---|---|---|
| LA | TOPS Online Application counts (the state aid application that satisfies the mandate in place of the FAFSA) by high school | Not published by school | LOSFA |
| IL | FAFSA + Alternative Application for Illinois Financial Aid completion by high school | Shared with districts only through ISAC's GAP Access portal | ISAC |
| IL | MAP grant recipients by high school | ISAC Data Books report MAP by college, not high school | ISAC |
| NJ | FAFSA + NJ Alternative Financial Aid Application (NJAFAA) completion by high school | Not in the School Performance Reports (checked through 2024-25) or on HESAA's site | HESAA or NJDOE |
| NJ | Tuition Aid Grant (TAG) recipients by high school | Not published by high school | HESAA |

Louisiana TOPS eligibility and recipients by high school are public (PDF) and downloaded to `LA/ldoe_tops/`.

## Replication package

`replication/deneault_2023/` holds Deneault (2023) code and README from openICPSR project 161021 V1, downloaded manually because openICPSR requires a login. Its `Raw-Data` folder, which includes files LDOE no longer posts (e.g. the class of 2013 ACT file), has not been added yet.
