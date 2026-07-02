from __future__ import annotations

import csv
import importlib
import json
import sys
from pathlib import Path

import pytest
import requests

import REvoDesign.magician.designers.openkinetics as openkinetics
from RosettaPy.common.mutation import Chain, RosettaPyProteinSequence
from REvoDesign.citations import CitationManager
from REvoDesign.magician.designers.openkinetics import (
    OpenKineticsClient,
    OpenKineticsConfigurationError,
    OpenKineticsTimeoutError,
    OpenKineticsValidationError,
    _normalize_result_rows,
    build_openkinetics_request_payload,
    get_method_metadata,
    load_chain_sequence_context,
    load_mutation_labels,
    relabel_pdb_position_to_sequential,
    resolve_substrate_metadata,
)
from REvoDesign.magician.designers.openkinetics._scorers import CataProKcatKmScorer

# Fixture-collection helpers live in scripts/dev/, not in the production package.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "dev"))
from _openkinetics_fixtures import collect_openkinetics_fixture_dataset  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
MUTATION_PATH = REPO_ROOT / "tests" / "data" / "mutations" / "1SUO.surf.entro.mutagenesis.besthits.mut.txt"
PDB_PATH = REPO_ROOT / "tests" / "data" / "pdb" / "1SUO.pdb"
FIXTURE_DIR = REPO_ROOT / "tests" / "data" / "kinetics" / "openkinetics_1SUO"

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _load_fixture(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def _load_csv_rows(name: str) -> list[dict[str, str]]:
    with (FIXTURE_DIR / name).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# Fakes for mocked HTTP
# ---------------------------------------------------------------------------


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


class _FailingSession:
    def request(self, method, url, json=None, timeout=None, headers=None):
        raise requests.ConnectionError("dns down")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_parse_1suo_mutation_labels():
    labels = load_mutation_labels(MUTATION_PATH)
    assert labels[:3] == ["AE93D", "AK191R", "AQ204E"]
    assert labels[-1] == "AE474A"
    assert len(labels) == 15


def test_build_variant_rows_uses_pdb_numbering():
    wt_sequences, sequence, residue_numbers = load_chain_sequence_context(PDB_PATH, chain_id="A")

    from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id

    # Convert PDB-numbered labels to sequential positions, then parse.
    seq_label_93 = relabel_pdb_position_to_sequential("AE93D", residue_numbers, chain_id="A")
    seq_label_191 = relabel_pdb_position_to_sequential("AK191R", residue_numbers, chain_id="A")
    mutant_93 = extract_mutants_from_mutant_id(seq_label_93, wt_sequences)
    mutant_191 = extract_mutants_from_mutant_id(seq_label_191, wt_sequences)

    # WT residue at PDB position 93 is E (sequential index in residue_numbers)
    assert sequence[residue_numbers.index(93)] == "E"
    # WT residue at PDB position 191 is K
    assert sequence[residue_numbers.index(191)] == "K"

    # Mutant at PDB position 93 has D
    seq_93 = mutant_93.mutated_sequence.get_sequence_by_chain(chain_id="A")
    assert seq_93[residue_numbers.index(93)] == "D"
    assert seq_93[residue_numbers.index(191)] == "K"

    # Mutant at PDB position 191 has R
    seq_191 = mutant_191.mutated_sequence.get_sequence_by_chain(chain_id="A")
    assert seq_191[residue_numbers.index(93)] == "E"
    assert seq_191[residue_numbers.index(191)] == "R"


def test_mutation_file_produces_wt_plus_all_point_mutants():
    labels = load_mutation_labels(MUTATION_PATH)
    wt_sequences, wt_sequence, residue_numbers = load_chain_sequence_context(PDB_PATH, chain_id="A")
    from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id

    variant_rows = [{"variant_id": "WT", "mutation": "WT", "protein_sequence": wt_sequence}]
    for label in labels:
        seq_label = relabel_pdb_position_to_sequential(label, residue_numbers, chain_id="A")
        mutant = extract_mutants_from_mutant_id(seq_label, wt_sequences)
        variant_seq = mutant.mutated_sequence.get_sequence_by_chain(chain_id="A")
        variant_rows.append({"variant_id": label, "mutation": label, "protein_sequence": variant_seq})

    assert len(variant_rows) == 16
    assert variant_rows[0]["variant_id"] == "WT"
    assert variant_rows[-1]["variant_id"] == "AE474A"


def test_resolve_substrate_metadata():
    """RDKit PDB-to-SMILES conversion for the 1SUO CPZ ligand.

    RDKit produces a simplified SMILES from the PDB block.  This may not
    perfectly match the canonical chlorpromazine SMILES, but the scorer
    uses whatever RDKit returns as-is — no manual fallback is applied."""
    metadata = resolve_substrate_metadata(PDB_PATH, structure_id="1SUO")
    assert metadata["ligand_identifier"] == "CPZ:A:600"
    assert metadata["smiles_resolution"] == "rdkit"
    # RDKit produces SOME SMILES string from the PDB block
    assert metadata["substrate_smiles"]
    assert len(metadata["substrate_smiles"]) > 3


def test_collect_openkinetics_fixture_dataset_dry_run(tmp_path):
    output_dir = tmp_path / "openkinetics_1SUO"
    result = collect_openkinetics_fixture_dataset(
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
    assert substrate_payload["substrate_smiles"]


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

    assert len(score_rows) == len(input_rows), (
        f"Fixture has {len(score_rows)} score rows for {len(input_rows)} variants. "
        "Add OPENKINETICS_API_KEY to environ.yaml, reload REvoDesign, then regenerate with: "
        "python scripts/dev/collect_openkinetics_fixtures.py --overwrite"
    )


def test_openkinetics_client_submit_uses_real_json_shape():
    session = _FakeSession(
        methods_response=_load_fixture("methods_response.json"),
        validate_response=_load_fixture("validate_response.json"),
        submit_response=_load_fixture("submit_response.json"),
        status_responses=_load_fixture("status_responses.json"),
        result_response=_load_fixture("result_response.json"),
    )
    client = OpenKineticsClient(session=session)
    client._require_api_key = lambda: "test-key"

    rows = [{"Protein Sequence": "AAA", "Substrate": "CCO"}]
    submit_response = client.submit(rows, method="CataPro", prediction_type="kcat/Km")
    assert submit_response["jobId"] == _load_fixture("submit_response.json")["jobId"]
    payload = session.submissions[0]
    assert payload["targets"] == ["kcat/Km"]
    assert payload["methods"] == {"kcat/Km": "CataPro"}
    assert payload["data"] == rows
    assert payload["useExperimental"] is False


def test_openkinetics_client_wraps_transport_errors():
    client = OpenKineticsClient(session=_FailingSession())
    client._require_api_key = lambda: "test-key"
    with pytest.raises(openkinetics.OpenKineticsAPIError, match="dns down"):
        client.list_methods()


def test_openkinetics_api_key_resolution_prefers_direct_key(monkeypatch):
    monkeypatch.setenv("OPENKINETICS_API_KEY", "env-key")
    client = OpenKineticsClient(api_key="direct-key")
    assert client._require_api_key() == "direct-key"


def test_openkinetics_api_key_resolution_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("OPENKINETICS_API_KEY", "env-key")
    client = OpenKineticsClient(api_key=None)
    assert client._require_api_key() == "env-key"


def test_openkinetics_scorer_normalizes_real_fixture_response(tmp_path):
    from REvoDesign.magician.designers.openkinetics._scorers import CataProKcatKmScorer

    session = _FakeSession(
        methods_response=_load_fixture("methods_response.json"),
        validate_response=_load_fixture("validate_response.json"),
        submit_response=_load_fixture("submit_response.json"),
        status_responses=_load_fixture("status_responses.json"),
        result_response=_load_fixture("result_response.json"),
    )
    scorer = CataProKcatKmScorer(
        client=OpenKineticsClient(session=session),
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
    assert (
        result["normalized_scores"][0]["predicted_value"]
        == _load_fixture("result_response.json")["data"][0]["kcat/Km (1/(s*mM))"]
    )


def test_openkinetics_parallel_scorer_batches_variants(tmp_path):
    from REvoDesign.magician.designers.openkinetics._scorers import CataProKcatKmScorer
    from REvoDesign.tools.mutant_tools import extract_mutants_from_mutant_id

    session = _FakeSession(
        methods_response=_load_fixture("methods_response.json"),
        validate_response=_load_fixture("validate_response.json"),
        submit_response=_load_fixture("submit_response.json"),
        status_responses=_load_fixture("status_responses.json"),
        result_response=_load_fixture("result_response.json"),
    )
    client = OpenKineticsClient(session=session)
    client._require_api_key = lambda: "test-key"
    scorer = CataProKcatKmScorer(client=client, cache_dir=str(tmp_path / "cache"), substrate_smiles="CCO")

    wt_sequences, _, residue_numbers = load_chain_sequence_context(PDB_PATH, chain_id="A")
    mutants = [
        extract_mutants_from_mutant_id(
            relabel_pdb_position_to_sequential(label, residue_numbers, chain_id="A"),
            wt_sequences,
        )
        for label in ("AE93D", "AK191R")
    ]

    scored = scorer.parallel_scorer(mutants, nproc=8)

    assert len(session.submissions) == 1
    assert len(session.submissions[0]["data"]) == 2
    assert [mutant.mutant_score for mutant in scored] == [
        _load_fixture("result_response.json")["data"][0]["kcat/Km (1/(s*mM))"],
        _load_fixture("result_response.json")["data"][1]["kcat/Km (1/(s*mM))"],
    ]


def test_openkinetics_sequence_selection_uses_configured_chain(tmp_path):
    scorer = CataProKcatKmScorer(cache_dir=str(tmp_path / "cache"), substrate_smiles="CCO", chain="B")
    sequence = RosettaPyProteinSequence([Chain("A", "AAAA"), Chain("B", "BBBB")])

    assert scorer._sequence_from_mutant(sequence) == ("variant", "BBBB")


def test_openkinetics_scorer_cache_hit(tmp_path):
    from REvoDesign.magician.designers.openkinetics._scorers import CataProKcatKmScorer

    CitationManager().clear()
    cache_dir = tmp_path / "cache"
    scorer = CataProKcatKmScorer(cache_dir=str(cache_dir))
    ck = scorer._variant_cache_key("AAAA", "CCO", scorer.default_method, scorer.default_prediction_type)
    scorer._write_variant_cache(
        ck,
        {
            "protein_sequence": "AAAA",
            "substrate_smiles": "CCO",
            "method": scorer.default_method,
            "prediction_type": scorer.default_prediction_type,
            "predicted_value": 1.23,
            "score_direction": "higher_is_better",
            "variant_id": "WT",
            "mutation": "WT",
            "job_id": "cached-job",
        },
    )
    # Verify the cache file is SQLite, not JSON
    assert (cache_dir / "variant_cache.db").is_file()
    result = scorer.score_variants(
        [{"variant_id": "WT", "mutation": "WT", "protein_sequence": "AAAA"}],
        substrate_smiles="CCO",
    )
    assert result["job_id"] == ""
    assert result["normalized_scores"][0]["predicted_value"] == 1.23
    assert "test-key" not in (cache_dir / "variant_cache.db").read_bytes().decode("latin-1")
    assert "OpenKineticsPredictor" in CitationManager().called_citations
    assert "CataPro" in CitationManager().called_citations


def test_openkinetics_predictor_classes_include_method_citations():
    from REvoDesign.magician.designers.openkinetics import CataProKcatKmScorer, EITLEMKmScorer

    assert "OpenKineticsPredictor" in CataProKcatKmScorer.__bibtex__
    assert "CataPro" in CataProKcatKmScorer.__bibtex__
    assert "10.1038/s41467-025-58038-4" in CataProKcatKmScorer.__bibtex__["CataPro"]
    assert "10.1016/j.checat.2024.101094" in EITLEMKmScorer.__bibtex__["EITLEM"]


def test_openkinetics_scorer_cache_writes_new_entries(tmp_path):
    """After a successful API call, fresh scores are written to the SQLite cache."""
    from REvoDesign.magician.designers.openkinetics._scorers import CataProKcatKmScorer

    session = _FakeSession(
        methods_response=_load_fixture("methods_response.json"),
        validate_response=_load_fixture("validate_response.json"),
        submit_response=_load_fixture("submit_response.json"),
        status_responses=_load_fixture("status_responses.json"),
        result_response=_load_fixture("result_response.json"),
    )

    cache_dir = tmp_path / "cache"
    client = OpenKineticsClient(session=session)
    client._require_api_key = lambda: "test-key"
    scorer = CataProKcatKmScorer(client=client, cache_dir=str(cache_dir))

    # Use a sequence present in the fixture result_response.
    seq = _load_fixture("result_response.json")["data"][0]["Protein Sequence"]
    result = scorer.score_variants(
        [{"variant_id": "WT", "mutation": "WT", "protein_sequence": seq}],
        substrate_smiles="CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21",
    )
    assert result["status"] == "completed"

    # Verify the fresh score was written to the SQLite cache DB.
    db_path = cache_dir / "variant_cache.db"
    assert db_path.is_file()
    import sqlite3

    with sqlite3.connect(str(db_path)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM variant_cache").fetchone()[0]
    assert count >= 1

    # Subsequent call with the same variant hits the cache (no API call needed).
    result2 = scorer.score_variants(
        [{"variant_id": "WT", "mutation": "WT", "protein_sequence": seq}],
        substrate_smiles="CN(C)CCCN1c2ccccc2Sc2ccc(Cl)cc21",
    )
    assert result2["normalized_scores"][0]["predicted_value"] == result["normalized_scores"][0]["predicted_value"]
    assert result2["job_id"] == ""  # all-cache: no job_id


def test_openkinetics_client_requires_api_key():
    client = OpenKineticsClient()
    with pytest.raises(OpenKineticsConfigurationError):
        client._require_api_key()


def test_methods_parsing_supports_unikp_and_rejects_invalid_combo():
    methods_response = _load_fixture("methods_response.json")
    method_metadata = get_method_metadata(methods_response, method="UniKP", prediction_type="kcat")
    assert method_metadata["id"] == "UniKP"
    method_metadata = get_method_metadata(methods_response, method="TurNup", prediction_type="kcat")
    assert method_metadata["id"] == "TurNup"
    with pytest.raises(OpenKineticsValidationError):
        get_method_metadata(methods_response, method="UniKP", prediction_type="kcat/Km")


def test_submit_payload_rejects_missing_method_required_columns():
    methods_response = _load_fixture("methods_response.json")
    method_metadata = get_method_metadata(methods_response, method="TurNup", prediction_type="kcat")

    with pytest.raises(OpenKineticsValidationError, match="Products, Substrates"):
        build_openkinetics_request_payload(
            data_rows=[{"Protein Sequence": "AAAA", "Substrate": "CCO"}],
            method_metadata=method_metadata,
            method="TurNup",
            prediction_type="kcat",
        )


def test_score_direction_tracks_prediction_type():
    km_rows = _normalize_result_rows(
        {
            "columns": ["Km"],
            "data": [{"Protein Sequence": "AAAA", "variant_id": "WT", "Km": 1.5}],
        },
        method="UniKP",
        prediction_type="Km",
        substrate_smiles="CCO",
        variant_rows=[{"variant_id": "WT", "mutation": "WT", "protein_sequence": "AAAA"}],
    )
    kcat_km_rows = _normalize_result_rows(
        {
            "columns": ["kcat/Km (1/(s*mM))"],
            "data": [{"Protein Sequence": "AAAA", "variant_id": "WT", "kcat/Km (1/(s*mM))": 1.5}],
        },
        method="CataPro",
        prediction_type="kcat/Km",
        substrate_smiles="CCO",
        variant_rows=[{"variant_id": "WT", "mutation": "WT", "protein_sequence": "AAAA"}],
    )
    assert km_rows[0]["score_direction"] == "lower_is_better"
    assert kcat_km_rows[0]["score_direction"] == "higher_is_better"


def test_malformed_result_raises_validation_error():
    with pytest.raises(OpenKineticsValidationError):
        _normalize_result_rows(
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
    client = OpenKineticsClient(session=session, timeout_seconds=0)
    client._require_api_key = lambda: "test-key"
    with pytest.raises(OpenKineticsTimeoutError):
        client.poll_until_complete("job-1", poll_interval_seconds=0, timeout_seconds=0)


def test_import_does_not_trigger_network_calls(monkeypatch):
    def _boom(*args, **kwargs):
        raise AssertionError("network should not be called during import")

    monkeypatch.setattr("requests.sessions.Session.request", _boom)
    # Re-import the openkinetics package fresh; must not touch the network.
    importlib.reload(openkinetics)
    assert hasattr(openkinetics, "CataProKcatKmScorer")
    assert not hasattr(openkinetics, "TurNupKcatScorer")
    assert hasattr(openkinetics, "UniKPKcatScorer")
    assert hasattr(openkinetics, "UniKPKmScorer")
