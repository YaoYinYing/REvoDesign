# PRIME vendored model code

The pinned Pro-Prime snapshots (`ProPrime_650M_OGT_Prediction-91490f95c707`,
`Prime_690M-7b75010748d2`) ship custom transformers model code inside their
weights directories. Loading them the usual way means `trust_remote_code=True`:
model-dir Python is imported and executed at task time. That is a
supply-chain code-execution path, and this runner does not use it.

Instead, the custom code is vendored into the image at build time, and
`run.sh`:

1. imports the vendored modules from `/opt/prime_model_code/<snapshot>/`,
2. registers them with `AutoConfig` / `AutoModel` / `AutoTokenizer`,
3. loads the weights with `trust_remote_code=False, local_files_only=True`.

The vendored modules are never fetched from the model directory. If the
vendored code is missing or broken, PRIME tasks fail loudly — there is no
fallback to executing weights-dir code.

## Vendoring the code (required before PRIME tasks can run)

For each pinned snapshot, copy the custom modules referenced by its
`config.json` `auto_map` (typically `modeling_*.py`, `tokenization_*.py`,
`configuration_*.py`) from the weights directory on the deploy host into the
snapshot's subdirectory here:

```
/mnt/db/weights/prime/ProPrime_650M_OGT_Prediction-91490f95c707/  ->  vendor/ProPrime_650M_OGT_Prediction-91490f95c707/
/mnt/db/weights/prime/Prime_690M-7b75010748d2/                   ->  vendor/Prime_690M-7b75010748d2/
```

Example:

```bash
for s in ProPrime_650M_OGT_Prediction-91490f95c707 Prime_690M-7b75010748d2; do
    mkdir -p "vendor/$s"
    cp /mnt/db/weights/prime/"$s"/modeling_*.py /mnt/db/weights/prime/"$s"/tokenization_*.py \
       /mnt/db/weights/prime/"$s"/configuration_*.py "vendor/$s/"
done
```

Then rebuild the image. If a snapshot's `config.json` references other
modules (check its `auto_map`), copy those too. Review and pin the vendored
copy — it is committed to the repo and run as-is.

## Optional integrity manifest

To pin the weights themselves, add `manifest.sha256` generated from the
weights root (paths relative to `/mnt/db/weights/prime`):

```bash
cd /mnt/db/weights/prime && \
sha256sum ProPrime_650M_OGT_Prediction-91490f95c707/* Prime_690M-7b75010748d2/* \
    > <repo>/server/docker/runners/prime/vendor/manifest.sha256
```

At task time `run.sh` verifies the mounted weights with
`sha256sum -c manifest.sha256` from the weights root; any mismatch fails the
task. Without the manifest, integrity is not checked.
