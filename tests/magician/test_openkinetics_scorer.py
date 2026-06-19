from __future__ import annotations

import csv
import json
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "src" / "REvoDesign" / "magician" / "designers" / "openkinetics.py"
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


def _load_csv_rows(name: str) -> list[dict[str, str]]:
    with (FIXTURE_DIR / name).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


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
    assert len(labels) == 15

    mutation = openkinetics.parse_point_mutation_label(labels[0])
    assert mutation.chain_id == "A"
    assert mutation.wt_res == "E"
    assert mutation.position == 93
    assert mutation.mut_res == "D"


def test_build_variant_rows_uses_pdb_numbering():
    _, sequence, residue_numbers = openkinetics.load_chain_sequence_context(PDB_PATH, chain_id="A")
    rows = openkinetics.build_variant_rows(sequence, residue_numbers, ["AE93D", "AK191R"], chain_id="A")

    assert rows[0]["variant_id"] == "WT"
    assert rows[0]["protein_sequence"] == sequence
    assert openkinetics.residue_at_pdb_position(sequence, residue_numbers, 93, "A") == "E"
    assert openkinetics.residue_at_pdb_position(sequence, residue_numbers, 191, "A") == "K"

    mutated_93 = rows[1]["protein_sequence"]
    assert mutated_93[openkinetics.residue_index_for_pdb_position(residue_numbers, 93, "A")] == "D"
    assert mutated_93[openkinetics.residue_index_for_pdb_position(residue_numbers, 191, "A")] == "K"

    mutated_191 = rows[2]["protein_sequence"]
    assert mutated_191[openkinetics.residue_index_for_pdb_position(residue_numbers, 93, "A")] == "E"
    assert mutated_191[openkinetics.residue_index_for_pdb_position(residue_numbers, 191, "A")] == "R"


def test_mutation_file_produces_wt_plus_all_point_mutants():
    labels = openkinetics.load_mutation_labels(MUTATION_PATH)
    _, sequence, residue_numbers = openkinetics.load_chain_sequence_context(PDB_PATH, chain_id="A")
    rows = openkinetics.build_variant_rows(sequence, residue_numbers, labels, chain_id="A")

    assert len(rows) == 16
    assert rows[0]["variant_id"] == "WT"
    assert rows[-1]["variant_id"] == "AE474A"


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
    )

    manifest = result["manifest"]
    assert manifest["dry_run"] is True
    assert manifest["number_of_mutations_parsed"] == 15
    assert manifest["number_of_variants_submitted"] == 16
    assert manifest["collection_limited"] is False
    assert manifest["ligand_identifier"] == "CPZ:A:600"
    assert manifest["ligand_id"] == "CPZ"

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
    assert "manual_fallback" in substrate_payload


def test_real_fixture_tables_cover_all_variants():
    manifest = _load_fixture("manifest.json")
    input_rows = _load_csv_rows("input_variants.csv")
    api_rows = _load_csv_rows("api_input.csv")
    score_rows = _load_csv_rows("normalized_scores.csv")

    assert manifest["openkinetics_method"] == "CataPro"
    assert manifest["prediction_type"] == "kcat/Km"
    assert manifest["number_of_mutations_parsed"] == 15
    assert manifest["number_of_variants_submitted"] == 16
    assert len(input_rows) == 16
    assert len(api_rows) == 16
    assert input_rows[0]["variant_id"] == "WT"
    assert input_rows[-1]["variant_id"] == "AE474A"
    if manifest.get("fixture_status") == "stale_partial_live_result":
        assert len(score_rows) < len(input_rows)
        assert "python scripts/dev/collect_openkinetics_fixtures.py --overwrite" in (
            FIXTURE_DIR / "README.md"
        ).read_text(encoding="utf-8")
    else:
        assert len(score_rows) == len(input_rows)


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


def test_openkinetics_api_key_resolution_prefers_direct_key(monkeypatch):
    monkeypatch.setenv("OPENKINETICS_API_KEY", "env-key")
    client = openkinetics.OpenKineticsClient(api_key="yaml-key", api_key_env="OPENKINETICS_API_KEY")
    assert client._require_api_key() == "yaml-key"


def test_openkinetics_api_key_resolution_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("OPENKINETICS_API_KEY", "env-key")
    client = openkinetics.OpenKineticsClient(api_key=None, api_key_env="OPENKINETICS_API_KEY")
    assert client._require_api_key() == "env-key"


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

    cache_files = list((tmp_path / "cache").glob("*.json"))
    assert cache_files
    assert "test-key" not in cache_files[0].read_text(encoding="utf-8")


def test_openkinetics_client_requires_api_key():
    client = openkinetics.OpenKineticsClient(api_key_env="OPENKINETICS_API_KEY")
    with pytest.raises(openkinetics.OpenKineticsConfigurationError):
        client._require_api_key()


def test_methods_parsing_supports_unikp_and_rejects_invalid_combo():
    methods_response = _load_fixture("methods_response.json")
    method_metadata = openkinetics.get_method_metadata(
        methods_response,
        method="UniKP",
        prediction_type="kcat",
    )
    assert method_metadata["id"] == "UniKP"
    with pytest.raises(openkinetics.OpenKineticsValidationError):
        openkinetics.get_method_metadata(
            methods_response,
            method="UniKP",
            prediction_type="kcat/Km",
        )


def test_score_direction_tracks_prediction_type():
    km_rows = openkinetics._normalize_result_rows(
        [{"variant_id": "WT", "prediction": 1.5, "protein_sequence": "AAAA"}],
        method="UniKP",
        prediction_type="Km",
        substrate_smiles="CCO",
        variant_rows=[{"variant_id": "WT", "mutation": "WT", "protein_sequence": "AAAA"}],
    )
    kcat_km_rows = openkinetics._normalize_result_rows(
        [{"variant_id": "WT", "prediction": 1.5, "protein_sequence": "AAAA"}],
        method="CataPro",
        prediction_type="kcat/Km",
        substrate_smiles="CCO",
        variant_rows=[{"variant_id": "WT", "mutation": "WT", "protein_sequence": "AAAA"}],
    )
    assert km_rows[0]["score_direction"] == "lower_is_better"
    assert kcat_km_rows[0]["score_direction"] == "higher_is_better"


def test_malformed_result_raises_validation_error():
    with pytest.raises(openkinetics.OpenKineticsValidationError):
        openkinetics._normalize_result_rows(
            {"jobId": "x"},
            method="CataPro",
            prediction_type="kcat/Km",
            substrate_smiles="CCO",
        )


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


def test_import_does_not_trigger_network_calls(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("network should not be called during import")

    monkeypatch.setattr("requests.sessions.Session.request", _boom)
    spec = importlib.util.spec_from_file_location("revodesign_openkinetics_import_check", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert hasattr(module, "OpenKineticsScorer")
