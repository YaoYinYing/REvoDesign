# OpenKinetics 1SUO Fixture

This directory is produced by `scripts/dev/collect_openkinetics_fixtures.py`.

- Structure: `1SUO`
- Mutation source: `/Users/yyy/Documents/protein_design/REvoDesign/tests/data/mutations/1SUO.surf.entro.mutagenesis.besthits.mut.txt`
- Ligand identifier: `CPZ:A:600`
- Substrate SMILES: `CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21`
- Method: `CataPro`
- Prediction type: `kcat/Km`
- API base URL: `https://predictor.openkinetics.org/api/v1`
- Collected at: `2026-06-19T01:57:16Z`
- Mutation count: `15`
- Variant count: `16`

Notes:
- API keys and Authorization headers are never stored here.
- The CPZ substrate uses a manually verified chlorpromazine SMILES fallback because direct PDB-to-SMILES conversion is not chemically reliable for this ligand.
- Schema assumption: Official API docs could not be fetched automatically during implementation; the collector uses the documented fallback endpoint pattern from plan/openkinetics.md.
- Fixture status: `stale_partial_live_result`
- The checked-in live prediction files still cover only WT plus three mutants from the earlier limited run.
- Regenerate the full live fixture with `export OPENKINETICS_API_KEY="..." && python scripts/dev/collect_openkinetics_fixtures.py --overwrite`.
