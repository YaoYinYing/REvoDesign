# OpenKinetics Test Fixtures

This directory is reserved for real and mocked OpenKinetics fixture data.

- The manual collection entry point is `scripts/dev/collect_openkinetics_fixtures.py`.
- The intended permanent real-data dataset path is `tests/data/kinetics/openkinetics_1SUO/`.
- Ordinary tests should only use checked-in fixture files and must not contact the live service.
- API keys must never be written anywhere under this directory.
- The offline input tables should contain WT plus all mutations from the source mutation file even when the checked-in live result subset is stale.

If the real fixture has not been collected yet, add `OPENKINETICS_API_KEY` to
the living `environ.yaml`, reload REvoDesign, then run:

```bash
python scripts/dev/collect_openkinetics_fixtures.py --overwrite
```
