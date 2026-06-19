from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "src" / "REvoDesign" / "evaluate" / "openkinetics.py"
MUTATION_PATH = REPO_ROOT / "tests" / "data" / "mutations" / "1SUO.surf.entro.mutagenesis.besthits.mut.txt"
PDB_PATH = REPO_ROOT / "tests" / "data" / "pdb" / "1SUO.pdb"
FIXTURE_DIR = REPO_ROOT / "tests" / "data" / "kinetics" / "openkinetics_1SUO"


def _load_openkinetics_module():
    spec = importlib.util.spec_from_file_location("revodesign_openkinetics", MODULE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load OpenKinetics module from {MODULE_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


openkinetics = _load_openkinetics_module()


def _load_fixture(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


class _FakeResponse:
    def __init__(self, payload, status_code=200, text=None):
        self._payload = payload
        self.status_code = status_code
        self.text = text if text is not None else json.dumps(payload)

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, *, methods_response, validate_response, submit_response, status_responses, result_response):
        self.methods_response = methods_response
        self.validate_response = validate_response
        self.submit_response = submit_response
        self.status_responses = list(status_responses)
        self.result_response = result_response
        self.submissions = []
        self.validate_calls = 0

    def request(self, method, url, json=None, timeout=None, headers=None):
        if url.endswith("/methods/"):
            return _FakeResponse(self.methods_response)
        if "/submit/" in url:
            self.submissions.append(json)
            return _FakeResponse(self.submit_response)
        if "/status/" in url:
            payload = self.status_responses.pop(0)
            return _FakeResponse(payload)
        if "/result/" in url:
            return _FakeResponse(self.result_response)
        raise AssertionError(f"Unexpected request URL: {url}")

    def post(self, url, timeout=None, headers=None, files=None, data=None):
        if "/validate/" not in url:
            raise AssertionError(f"Unexpected post URL: {url}")
        self.validate_calls += 1
        assert data == {"runSimilarity": "false"}
        assert "file" in files
        return _FakeResponse(self.validate_response)

    def get(self, url, timeout=None, headers=None):
        raise AssertionError(f"Unexpected get URL: {url}")


def test_parse_1suo_mutation_labels():
    labels = openkinetics.load_mutation_labels(MUTATION_PATH)
    assert labels[:3] == ["AE93D", "AK191R", "AQ204E"]
    assert labels[-1] == "AE474A"

    mutation = openkinetics.parse_point_mutation_label(labels[0])
    assert mutation.chain_id == "A"
    assert mutation.wt_res == "E"
    assert mutation.position == 93
    assert mutation.mut_res == "D"


def test_build_variant_rows_uses_pdb_numbering():
    sequence = openkinetics.ProteinChainSequence.from_pdb(PDB_PATH, chain_id="A")
    rows = openkinetics.build_variant_rows(sequence, ["AE93D", "AK191R"])

    assert rows[0]["variant_id"] == "WT"
    assert rows[0]["protein_sequence"] == sequence.sequence
    assert sequence.residue_at(93) == "E"
    assert sequence.residue_at(191) == "K"

    mutated_93 = rows[1]["protein_sequence"]
    assert mutated_93[sequence.residue_index(93)] == "D"
    assert mutated_93[sequence.residue_index(191)] == "K"

    mutated_191 = rows[2]["protein_sequence"]
    assert mutated_191[sequence.residue_index(93)] == "E"
    assert mutated_191[sequence.residue_index(191)] == "R"


def test_resolve_substrate_metadata_uses_cpz_manual_fallback():
    metadata = openkinetics.resolve_substrate_metadata(PDB_PATH, structure_id="1SUO")
    assert metadata["ligand_identifier"] == "CPZ:A:600"
    assert metadata["substrate_smiles"] == "CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21"
    assert metadata["smiles_resolution"] == "manual_fallback"
    assert metadata["automatic_smiles"] == "ClC1CCC(C2CNCN2)CC1"


def test_collect_openkinetics_fixture_dataset_dry_run(tmp_path):
    output_dir = tmp_path / "openkinetics_1SUO"
    result = openkinetics.collect_openkinetics_fixture_dataset(
        mutation_path=MUTATION_PATH,
        pdb_path=PDB_PATH,
        output_dir=output_dir,
        dry_run=True,
        overwrite=True,
        limit=3,
    )

    manifest = result["manifest"]
    assert manifest["dry_run"] is True
    assert manifest["number_of_variants_submitted"] == 4
    assert manifest["ligand_identifier"] == "CPZ:A:600"

    input_variants = output_dir / "input_variants.csv"
    substrate = output_dir / "substrate.json"
    readme = output_dir / "README.md"
    manifest_path = output_dir / "manifest.json"

    assert input_variants.is_file()
    assert substrate.is_file()
    assert readme.is_file()
    assert manifest_path.is_file()

    substrate_payload = json.loads(substrate.read_text(encoding="utf-8"))
    assert substrate_payload["substrate_smiles"] == "CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21"


def test_real_fixture_manifest_and_scores_exist():
    manifest = _load_fixture("manifest.json")
    assert manifest["openkinetics_method"] == "CataPro"
    assert manifest["prediction_type"] == "kcat/Km"
    assert manifest["number_of_variants_submitted"] == 4
    assert (FIXTURE_DIR / "normalized_scores.csv").is_file()


def test_openkinetics_client_submit_uses_real_json_shape():
    session = _FakeSession(
        methods_response=_load_fixture("methods_response.json"),
        validate_response=_load_fixture("validate_response.json"),
        submit_response=_load_fixture("submit_response.json"),
        status_responses=_load_fixture("status_responses.json"),
        result_response=_load_fixture("result_response.json"),
    )
    client = openkinetics.OpenKineticsClient(
        api_key_env="OPENKINETICS_API_KEY",
        session=session,
    )
    client._require_api_key = lambda: "test-key"

    rows = [
        {
            "Protein Sequence": "AAA",
            "Substrate": "CCO",
        }
    ]
    job_id = client.submit(rows, method="CataPro", prediction_type="kcat/Km")
    assert job_id == _load_fixture("submit_response.json")["jobId"]
    payload = session.submissions[0]
    assert payload["targets"] == ["kcat/Km"]
    assert payload["methods"] == {"kcat/Km": "CataPro"}
    assert payload["data"] == rows


def test_openkinetics_scorer_normalizes_real_fixture_response(tmp_path):
    session = _FakeSession(
        methods_response=_load_fixture("methods_response.json"),
        validate_response=_load_fixture("validate_response.json"),
        submit_response=_load_fixture("submit_response.json"),
        status_responses=_load_fixture("status_responses.json"),
        result_response=_load_fixture("result_response.json"),
    )
    scorer = openkinetics.OpenKineticsScorer(
        client=openkinetics.OpenKineticsClient(session=session),
        cache_dir=str(tmp_path / "cache"),
    )
    scorer.client._require_api_key = lambda: "test-key"

    variants = [
        {
            "variant_id": "WT",
            "mutation": "WT",
            "protein_sequence": _load_fixture("result_response.json")["data"][0]["Protein Sequence"],
        },
        {
            "variant_id": "AE93D",
            "mutation": "AE93D",
            "protein_sequence": _load_fixture("result_response.json")["data"][1]["Protein Sequence"],
        },
    ]
    result = scorer.score_variants(
        variants,
        substrate_smiles="CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21",
        method="CataPro",
        prediction_type="kcat/Km",
    )
    assert result["job_id"] == _load_fixture("submit_response.json")["jobId"]
    assert result["normalized_scores"][0]["variant_id"] == "WT"
    assert result["normalized_scores"][0]["predicted_value"] == _load_fixture("result_response.json")["data"][0][
        "kcat/Km (1/(s*mM))"
    ]


def test_openkinetics_scorer_cache_hit(tmp_path):
    cache_dir = tmp_path / "cache"
    scorer = openkinetics.OpenKineticsScorer(cache_dir=str(cache_dir))
    cached_payload = {
        "job_id": "cached-job",
        "status": "completed",
        "normalized_scores": [{"variant_id": "WT", "predicted_value": 1.23}],
        "raw_result": {"ok": True},
        "status_responses": [],
    }
    local_rows, api_rows = scorer._prepare_rows(
        [{"variant_id": "WT", "mutation": "WT", "protein_sequence": "AAAA"}],
        "CCO",
    )
    cache_key = openkinetics._stable_cache_key(
        {
            "base_url": scorer.client.base_url,
            "method": scorer.default_method,
            "prediction_type": scorer.default_prediction_type,
            "rows": api_rows,
        }
    )
    scorer._write_cache(cache_key, cached_payload)
    result = scorer.score_variants(
        [{"variant_id": "WT", "mutation": "WT", "protein_sequence": "AAAA"}],
        substrate_smiles="CCO",
    )
    assert result["job_id"] == "cached-job"
    assert result["normalized_scores"][0]["predicted_value"] == 1.23


def test_openkinetics_client_requires_api_key():
    client = openkinetics.OpenKineticsClient(api_key_env="OPENKINETICS_API_KEY")
    with pytest.raises(openkinetics.OpenKineticsConfigurationError):
        client._require_api_key()


def test_openkinetics_poll_timeout():
    session = _FakeSession(
        methods_response=_load_fixture("methods_response.json"),
        validate_response=_load_fixture("validate_response.json"),
        submit_response=_load_fixture("submit_response.json"),
        status_responses=[
            {"status": "Processing"},
            {"status": "Processing"},
            {"status": "Processing"},
        ],
        result_response=_load_fixture("result_response.json"),
    )
    client = openkinetics.OpenKineticsClient(session=session, timeout_seconds=0)
    client._require_api_key = lambda: "test-key"
    with pytest.raises(openkinetics.OpenKineticsTimeoutError):
        client.poll_until_complete("job-1", poll_interval_seconds=0, timeout_seconds=0)
