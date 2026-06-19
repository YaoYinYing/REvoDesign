# OpenKinetics Test Fixtures

This directory is reserved for real and mocked OpenKinetics fixture data.

- The manual collection entry point is `scripts/dev/collect_openkinetics_fixtures.py`.
- The intended permanent real-data dataset path is `tests/data/kinetics/openkinetics_1SUO/`.
- Ordinary tests should only use checked-in fixture files and must not contact the live service.
- API keys must never be written anywhere under this directory.

If the real fixture has not been collected yet, run the collector manually with:

```bash
OPENKINETICS_API_KEY="..." python scripts/dev/collect_openkinetics_fixtures.py --overwrite
```
