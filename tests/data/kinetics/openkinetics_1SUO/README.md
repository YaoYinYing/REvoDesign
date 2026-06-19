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

Notes:
- API keys and Authorization headers are never stored here.
- Schema assumption: Official API docs could not be fetched automatically during implementation; the collector uses the documented fallback endpoint pattern from plan/openkinetics.md.
