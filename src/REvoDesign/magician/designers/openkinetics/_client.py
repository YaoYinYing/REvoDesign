# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""OpenKinetics HTTP client, configuration, and API result normalization."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests
from omegaconf import OmegaConf

from REvoDesign import ROOT_LOGGER, reload_config_file

from ._models import (
    DEFAULT_OPENKINETICS_API_KEY_ENV,
    OPENKINETICS_ENDPOINTS,
    OpenKineticsAPIError,
    OpenKineticsConfigurationError,
    OpenKineticsTimeoutError,
    OpenKineticsValidationError,
)

logging = ROOT_LOGGER.getChild(__name__)

# ---------------------------------------------------------------------------
# Configuration loading
# ---------------------------------------------------------------------------


def load_openkinetics_config() -> Any:
    """Load OpenKinetics config from ``third_party/scorers/openkinetics_api.yaml``."""
    scorers = reload_config_file("third_party/scorers/openkinetics_api")["third_party"]["scorers"]
    return scorers.get("openkinetics") or scorers["scorers"]["openkinetics"]


def _api_key_management_base_url(base_url: str) -> str:
    parsed = urlsplit(base_url.rstrip("/"))
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[: -len("/v1")]
    if not path.endswith("/api"):
        path = "/api"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def persist_openkinetics_api_key(api_key: str) -> str:
    """Persist an OpenKinetics API key and register it for this process."""
    api_key = (api_key or "").strip()
    if not api_key:
        raise OpenKineticsConfigurationError("Cannot persist an empty OpenKinetics API key.")

    logging.info("Persisting OpenKinetics API key as %s.", DEFAULT_OPENKINETICS_API_KEY_ENV)
    os.environ[DEFAULT_OPENKINETICS_API_KEY_ENV] = api_key
    logging.debug("OpenKinetics API key registered in the current process environment.")

    try:
        from REvoDesign import ConfigBus
        from REvoDesign.driver.environ_register import register_environment_variables

        if ConfigBus._instance is not None:
            logging.debug("ConfigBus is initialized; updating environ.yaml through ConfigBus.")
            bus = ConfigBus()
            bus.set_value(
                f"variables.{DEFAULT_OPENKINETICS_API_KEY_ENV}",
                api_key,
                cfg="environ",
                force_add=True,
            )
            bus.cfg_group["environ"].save()
            register_environment_variables()
            logging.info("OpenKinetics API key saved to environ.yaml and applied immediately.")
            return api_key
    except Exception as exc:
        logging.debug("OpenKinetics API key persistence through ConfigBus failed.", exc_info=True)
        raise OpenKineticsConfigurationError("Failed to persist OpenKinetics API key to environ.yaml.") from exc

    from REvoDesign.bootstrap import REVODESIGN_CONFIG_DIR

    environ_path = Path(REVODESIGN_CONFIG_DIR) / "environ.yaml"
    logging.debug("ConfigBus is not initialized; writing OpenKinetics API key directly to %s.", environ_path)
    environ_path.parent.mkdir(parents=True, exist_ok=True)
    config = OmegaConf.load(environ_path) if environ_path.exists() else OmegaConf.create({"variables": {}})
    OmegaConf.update(config, f"variables.{DEFAULT_OPENKINETICS_API_KEY_ENV}", api_key, force_add=True)
    OmegaConf.save(config, environ_path)
    logging.info("OpenKinetics API key saved to %s and applied immediately.", environ_path)
    return api_key


def fetch_openkinetics_api_key(
    *,
    base_url: str | None = None,
    timeout_seconds: int | None = None,
    session: requests.Session | None = None,
    replace_existing: bool = False,
) -> str:
    """Generate a self-service OpenKinetics API key for the current client IP."""
    config = load_openkinetics_config()
    resolved_base_url = str(base_url or config["base_url"]).rstrip("/")
    timeout = int(timeout_seconds or config["timeout_seconds"])
    http = session or requests.Session()
    key_base_url = _api_key_management_base_url(resolved_base_url)
    logging.info("Requesting self-service OpenKinetics API key from %s.", key_base_url)
    logging.debug(
        "OpenKinetics API key request settings: base_url=%s timeout_seconds=%s replace_existing=%s",
        resolved_base_url,
        timeout,
        replace_existing,
    )

    def _post(path: str) -> requests.Response:
        logging.debug("OpenKinetics API key POST %s%s", key_base_url, path)
        try:
            response = http.post(f"{key_base_url}{path}", timeout=timeout)
        except requests.RequestException as exc:
            logging.debug("OpenKinetics API key POST failed.", exc_info=True)
            raise OpenKineticsAPIError(f"OpenKinetics API key request failed: {exc}") from exc
        logging.debug("OpenKinetics API key POST returned HTTP %s.", response.status_code)
        return response

    response = _post("/api-key/generate/")
    if response.status_code == 409 and replace_existing:
        logging.info("OpenKinetics reports an active API key; revoking because replace_existing=True.")
        revoke_response = _post("/api-key/revoke/")
        if revoke_response.status_code >= 400:
            raise OpenKineticsAPIError(
                f"OpenKinetics API key revoke failed: {revoke_response.status_code} {revoke_response.text[:200]}"
            )
        logging.debug("OpenKinetics active API key revoked; generating a replacement.")
        response = _post("/api-key/generate/")

    if response.status_code == 409:
        logging.info("OpenKinetics reports an active API key for this IP; not revoking automatically.")
        raise OpenKineticsConfigurationError(
            "OpenKinetics reports an active API key for this IP, but the full key is not available locally. "
            f"Add {DEFAULT_OPENKINETICS_API_KEY_ENV} to environ.yaml or regenerate with replace_existing=True."
        )
    if response.status_code >= 400:
        logging.debug("OpenKinetics API key generation failed with response body: %s", response.text[:200])
        raise OpenKineticsAPIError(
            f"OpenKinetics API key generation failed: {response.status_code} {response.text[:200]}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise OpenKineticsAPIError("OpenKinetics API key endpoint returned a non-JSON response") from exc

    generated_key = str(payload.get("key") or "").strip()
    if not generated_key:
        raise OpenKineticsAPIError("OpenKinetics API key endpoint did not return a key")
    logging.info("OpenKinetics API key generated successfully; key value is redacted.")
    return generated_key


def resolve_api_key(
    *,
    api_key: str | None = None,
    auto_register: bool = False,
    replace_existing: bool = False,
    base_url: str | None = None,
    timeout_seconds: int | None = None,
    session: requests.Session | None = None,
) -> str:
    direct_api_key = (api_key or "").strip()
    if direct_api_key:
        logging.debug("Using directly supplied OpenKinetics API key.")
        return direct_api_key

    env_api_key = os.environ.get(DEFAULT_OPENKINETICS_API_KEY_ENV, "").strip()
    if env_api_key:
        logging.debug("Using OpenKinetics API key from %s.", DEFAULT_OPENKINETICS_API_KEY_ENV)
        return env_api_key

    if auto_register:
        logging.info("No local OpenKinetics API key found; auto-registration is enabled.")
        return persist_openkinetics_api_key(
            fetch_openkinetics_api_key(
                base_url=base_url,
                timeout_seconds=timeout_seconds,
                session=session,
                replace_existing=replace_existing,
            )
        )

    logging.info("No OpenKinetics API key found and auto-registration is disabled.")
    raise OpenKineticsConfigurationError(
        f"Missing OpenKinetics API key. Add {DEFAULT_OPENKINETICS_API_KEY_ENV} to environ.yaml or enable "
        "OpenKinetics API key auto-registration."
    )


# ---------------------------------------------------------------------------
# Data I/O helpers
# ---------------------------------------------------------------------------


def write_csv_rows(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise OpenKineticsValidationError(f"No rows were provided for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_normalized_scores_csv(path: str | Path, rows: list[dict[str, Any]]) -> None:
    write_csv_rows(Path(path), rows)


# ---------------------------------------------------------------------------
# JSON utilities
# ---------------------------------------------------------------------------


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


# ---------------------------------------------------------------------------
# Request payload helpers
# ---------------------------------------------------------------------------


def build_openkinetics_data_rows(
    variant_rows: list[dict[str, str]],
    substrate_smiles: str,
) -> list[dict[str, str]]:
    return [
        {
            "Protein Sequence": row["protein_sequence"],
            "Substrate": substrate_smiles,
        }
        for row in variant_rows
    ]


def get_method_metadata(
    methods_response: dict[str, Any],
    *,
    method: str,
    prediction_type: str,
) -> dict[str, Any]:
    methods_by_prediction = methods_response.get("methods", {})
    if not isinstance(methods_by_prediction, dict):
        raise OpenKineticsValidationError("OpenKinetics methods response did not include a methods mapping")

    candidates = methods_by_prediction.get(prediction_type, [])
    if not isinstance(candidates, list):
        raise OpenKineticsValidationError(
            f"OpenKinetics methods response had an invalid entry for prediction type {prediction_type!r}"
        )

    for candidate in candidates:
        if candidate.get("id") == method or candidate.get("displayName") == method:
            return candidate

    raise OpenKineticsValidationError(f"Method {method!r} is not available for prediction type {prediction_type!r}")


def build_openkinetics_request_payload(
    *,
    data_rows: list[dict[str, str]],
    method_metadata: dict[str, Any],
    method: str,
    prediction_type: str,
) -> dict[str, Any]:
    required_columns = method_metadata.get("requiredColumns") or []
    if isinstance(required_columns, list) and required_columns:
        missing_columns = sorted(
            {
                str(column_name)
                for column_name in required_columns
                if any(str(column_name) not in row for row in data_rows)
            }
        )
        if missing_columns:
            raise OpenKineticsValidationError(
                f"Method {method!r} for {prediction_type!r} requires columns: {', '.join(missing_columns)}"
            )

    return {
        "data": data_rows,
        "targets": [prediction_type],
        "methods": {prediction_type: method_metadata.get("id", method)},
        "handleLongSequences": "truncate",
        "useExperimental": False,
        "includeSimilarityColumns": True,
        "canonicalizeSubstrates": True,
    }


# ---------------------------------------------------------------------------
# Result normalization
# ---------------------------------------------------------------------------

# The API returns a JSON object with ``columns`` (list of column-name strings)
# and ``data`` (list of per-variant dicts keyed by column name).  The job
# identifier is always the camelCase ``jobId`` field.  Protein sequences use
# the ``Protein Sequence`` column name.  These shapes are confirmed by the
# real fixture collected from the live API.


def _normalize_result_rows(
    result_payload: Any,
    *,
    method: str,
    prediction_type: str,
    substrate_smiles: str,
    variant_rows: list[dict[str, str]] | None = None,
    job_id: str = "",
) -> list[dict[str, Any]]:
    if not isinstance(result_payload, dict):
        raise OpenKineticsValidationError("OpenKinetics result payload must be a JSON object")

    result_columns = result_payload.get("columns")
    if not isinstance(result_columns, list) or not isinstance(result_payload.get("data"), list):
        raise OpenKineticsValidationError("OpenKinetics result payload must contain 'columns' and 'data' lists")

    records: list[Any] = result_payload["data"]
    score_direction = "lower_is_better" if prediction_type.lower() == "km" else "higher_is_better"

    variant_lookup: dict[str, dict[str, str]] = {}
    if variant_rows:
        variant_lookup = {row["protein_sequence"]: row for row in variant_rows if row.get("protein_sequence")}

    # Identify the column that holds the predicted value for this prediction_type.
    score_column: str | None = None
    result_payload_job_id: str = result_payload.get("jobId") or ""
    for column_name in result_columns:
        if isinstance(column_name, str) and column_name.lower().startswith(prediction_type.lower()):
            score_column = column_name
            break

    normalized_rows: list[dict[str, Any]] = []
    for record in records:
        if not isinstance(record, dict):
            raise OpenKineticsValidationError("Each prediction record must be a JSON object")

        protein_sequence = record.get("Protein Sequence") or ""
        matched_variant = variant_lookup.get(protein_sequence, {})
        variant_id = record.get("variant_id") or matched_variant.get("variant_id") or "unknown"
        mutation = record.get("mutation") or matched_variant.get("mutation") or variant_id
        row_job_id = record.get("job_id") or result_payload_job_id or job_id

        predicted_value: Any = None
        for key in (score_column, "predicted_value", prediction_type):
            if key and key in record:
                predicted_value = record[key]
                break
        if predicted_value is None:
            raise OpenKineticsValidationError(f"Unable to locate predicted value for record {variant_id!r}")

        normalized_rows.append(
            {
                "variant_id": variant_id,
                "mutation": mutation,
                "method": method,
                "prediction_type": prediction_type,
                "predicted_value": predicted_value,
                "score_direction": score_direction,
                "protein_sequence": protein_sequence,
                "substrate_smiles": substrate_smiles,
                "job_id": row_job_id,
                "status": record.get("status") or "completed",
                "source": "openkinetics_api",
            }
        )
    return normalized_rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_hard_http_error(error_message: str) -> bool:
    """Return True if *error_message* contains a non-409 HTTP status code.

    ``_request`` raises ``OpenKineticsAPIError`` with a message like
    ``"OpenKinetics API request failed: 409 {body}"`` for HTTP errors or
    ``"OpenKinetics API request failed: <exception>"`` for transport errors.
    Only HTTP responses with a status code other than 409 are "hard" errors.
    """
    prefix = "OpenKinetics API request failed: "
    if not error_message.startswith(prefix):
        return False
    tail = error_message[len(prefix) :]
    code_str = tail.split(" ", 1)[0]
    return code_str.isdigit() and code_str != "409"


# ---------------------------------------------------------------------------
# HTTP client
# ---------------------------------------------------------------------------


class OpenKineticsClient:
    """HTTP client for the OpenKinetics Predictor REST API.

    Used by both the scoring workflow (``OpenKineticsScorerAbstract``)
    and the manual fixture-collection workflow
    (``collect_openkinetics_fixture_dataset``).
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        auto_register_api_key: bool = False,
        replace_existing_api_key: bool = False,
        timeout_seconds: int | None = None,
        session: requests.Session | None = None,
    ) -> None:
        config = load_openkinetics_config()
        resolved_base_url = str(base_url or config["base_url"]).rstrip("/")

        self.base_url = resolved_base_url
        self.api_key = api_key or None
        self.auto_register_api_key = auto_register_api_key
        self.replace_existing_api_key = replace_existing_api_key
        self.timeout_seconds = int(timeout_seconds or config["timeout_seconds"])
        self.session = session or requests.Session()

    # -- credential helpers -------------------------------------------------

    def _require_api_key(self) -> str:
        return resolve_api_key(
            api_key=self.api_key,
            auto_register=self.auto_register_api_key,
            replace_existing=self.replace_existing_api_key,
            base_url=self.base_url,
            timeout_seconds=self.timeout_seconds,
            session=self.session,
        )

    # -- low-level request --------------------------------------------------

    def _request(self, method: str, path: str, *, json_payload: Any | None = None, timeout: float | None = None) -> Any:
        api_key = self._require_api_key()
        # Default to a short per-request timeout so a hung connection doesn't
        # block the caller for the full job timeout.  Submit/poll callers that
        # genuinely need patience pass an explicit timeout.
        effective_timeout = timeout if timeout is not None else 30.0
        for attempt in range(3):
            try:
                response = self.session.request(
                    method=method,
                    url=f"{self.base_url}{path}",
                    json=json_payload,
                    timeout=effective_timeout,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
                break
            except requests.RequestException as exc:
                if attempt == 2:
                    raise OpenKineticsAPIError(f"OpenKinetics API request failed: {exc}") from exc
                time.sleep(1)
        if response.status_code >= 400:
            raise OpenKineticsAPIError(f"OpenKinetics API request failed: {response.status_code} {response.text[:200]}")

        try:
            return response.json()
        except ValueError as exc:
            raise OpenKineticsAPIError("OpenKinetics API returned a non-JSON response") from exc

    # -- public API methods -------------------------------------------------

    def list_methods(self) -> Any:
        return self._request("GET", OPENKINETICS_ENDPOINTS["methods"])

    def validate_file(
        self,
        csv_path: str | Path,
        *,
        run_similarity: bool = False,
    ) -> Any:
        api_key = self._require_api_key()
        with Path(csv_path).open("rb") as handle:
            try:
                response = self.session.post(
                    f"{self.base_url}{OPENKINETICS_ENDPOINTS['validate']}",
                    timeout=self.timeout_seconds,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "application/json",
                    },
                    files={"file": handle},
                    data={"runSimilarity": "true" if run_similarity else "false"},
                )
            except requests.RequestException as exc:
                raise OpenKineticsAPIError(f"OpenKinetics API request failed: {exc}") from exc
        if response.status_code >= 400:
            raise OpenKineticsAPIError(f"OpenKinetics API request failed: {response.status_code} {response.text[:200]}")
        return response.json()

    def validate(
        self,
        rows: list[dict[str, Any]],
        *,
        run_similarity: bool = False,
    ) -> dict[str, Any]:
        self._normalize_score_variants_input(rows)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", suffix=".csv", delete=False) as handle:
            temp_path = Path(handle.name)
        try:
            write_csv_rows(
                temp_path,
                [
                    {
                        "Protein Sequence": str(row["protein_sequence"]),
                        "Substrate": str(row.get("Substrate", row.get("substrate_smiles", ""))),
                    }
                    for row in rows
                ],
            )
            return self.validate_file(temp_path, run_similarity=run_similarity)
        finally:
            temp_path.unlink(missing_ok=True)

    def check_health(self) -> dict[str, Any]:
        """Check the OpenKinetics service health endpoint."""
        return self._request("GET", OPENKINETICS_ENDPOINTS["health"])

    def check_quota(self) -> dict[str, Any]:
        """Check the account quota (daily usage / limit)."""
        return self._request("GET", OPENKINETICS_ENDPOINTS["quota"])

    def submit(
        self,
        rows: list[dict[str, Any]],
        method: str,
        prediction_type: str,
        *,
        handle_long_sequences: str = "truncate",
        use_experimental: bool = False,
        include_similarity_columns: bool = True,
        canonicalize_substrates: bool = True,
    ) -> dict[str, Any]:
        if not rows:
            raise OpenKineticsValidationError("At least one row is required for submission")
        methods_response = self.list_methods()
        method_metadata = get_method_metadata(methods_response, method=method, prediction_type=prediction_type)
        # Resolve the substrate column name from the method's required columns so
        # we match whatever the API expects ("Substrate" vs "Substrates" etc.).
        required_columns: list[str] = method_metadata.get("requiredColumns") or []
        substrate_col = "Substrates"
        for col in required_columns:
            if col not in ("Protein Sequence",) and "substrat" in col.lower():
                substrate_col = col
                break
        payload = build_openkinetics_request_payload(
            data_rows=[
                {
                    "Protein Sequence": str(row.get("Protein Sequence", row.get("protein_sequence", ""))),
                    substrate_col: str(row.get("Substrate", row.get(substrate_col, ""))),
                }
                for row in rows
            ],
            method_metadata=method_metadata,
            method=method,
            prediction_type=prediction_type,
        )
        payload["handleLongSequences"] = handle_long_sequences
        payload["useExperimental"] = use_experimental
        payload["includeSimilarityColumns"] = include_similarity_columns
        payload["canonicalizeSubstrates"] = canonicalize_substrates

        logging.info("OpenKinetics service health: %s", self.check_health())
        submit_response = self._request(
            "POST", OPENKINETICS_ENDPOINTS["submit"], json_payload=payload, timeout=self.timeout_seconds
        )
        job_id = submit_response.get("jobId")
        if not job_id:
            raise OpenKineticsValidationError("Submit response did not contain a job identifier (jobId)")
        logging.info("OpenKinetics job submitted: %s (method=%s, type=%s)", job_id, method, prediction_type)
        return submit_response

    def get_status(self, job_id: str) -> dict[str, Any]:
        return self._request("GET", OPENKINETICS_ENDPOINTS["status"].format(job_id=job_id))

    def get_result(
        self,
        job_id: str,
        result_format: str = "json",
        *,
        poll_interval_seconds: int = 3,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any] | str:
        path = OPENKINETICS_ENDPOINTS["result"].format(job_id=job_id)
        if result_format == "json":
            # ponytail: the API can report status=Completed a moment
            # before /result/ is materialized (409).  Retry with
            # backoff bounded by the remaining timeout budget.
            # Transient network errors are also retried; hard HTTP
            # errors (non-409 4xx/5xx) raise immediately.
            deadline = time.monotonic() + (timeout_seconds if timeout_seconds is not None else 30)
            delay = poll_interval_seconds
            while True:
                try:
                    _remaining = max(1.0, deadline - time.monotonic())
                    return self._request("GET", f"{path}?format=json", timeout=min(30.0, _remaining))
                except OpenKineticsAPIError as exc:
                    if _is_hard_http_error(str(exc)):
                        raise
                    # 409 or network — retryable.
                if time.monotonic() + delay > deadline:
                    raise OpenKineticsTimeoutError(f"Timed out waiting for OpenKinetics result {job_id}")
                logging.info("OpenKinetics result not ready for job %s, retrying in %ds...", job_id, delay)
                time.sleep(delay)
                delay = min(delay * 2, 30)
        if result_format == "csv":
            api_key = self._require_api_key()
            try:
                response = self.session.get(
                    f"{self.base_url}{path}",
                    timeout=self.timeout_seconds,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "text/csv",
                    },
                )
            except requests.RequestException as exc:
                raise OpenKineticsAPIError(f"OpenKinetics API request failed: {exc}") from exc
            if response.status_code >= 400:
                raise OpenKineticsAPIError(
                    f"OpenKinetics API request failed: {response.status_code} {response.text[:200]}"
                )
            return response.text
        raise OpenKineticsValidationError(f"Unsupported result_format: {result_format!r}")

    def poll_until_complete(
        self,
        job_id: str,
        *,
        poll_interval_seconds: int = 3,
        timeout_seconds: int = 600,
    ) -> list[Any]:
        started = time.monotonic()
        responses: list[Any] = []
        _last_logged_elapsed: int | None = None
        while True:
            status_payload = self.get_status(job_id)
            responses.append(status_payload)

            top_level_status = str(status_payload.get("status", "")).strip()
            elapsed = status_payload.get("elapsedSeconds", 0)
            queue_s = status_payload.get("queueSeconds")
            compute_s = status_payload.get("computeSeconds")
            queue_pos = status_payload.get("queuePosition")
            progress = status_payload.get("progress", {})

            # Log on every status change or every ~30 s of elapsed wall-clock.
            if top_level_status and (_last_logged_elapsed is None or abs((elapsed or 0) - _last_logged_elapsed) >= 30):
                _last_logged_elapsed = int(elapsed or 0)
                parts = [f"status={top_level_status}", f"elapsed={elapsed}s"]
                if queue_s is not None:
                    parts.append(f"queue={queue_s}s")
                if compute_s is not None:
                    parts.append(f"compute={compute_s}s")
                if queue_pos is not None:
                    parts.append(f"queuePosition={queue_pos}")
                if progress:
                    parts.append(
                        "progress="
                        f"{progress.get('moleculesProcessed', 0)}/{progress.get('moleculesTotal', 0)} mol, "
                        f"{progress.get('predictionsMade', 0)}/{progress.get('predictionsTotal', 0)} pred"
                    )
                logging.info("OpenKinetics job %s: %s", job_id, ", ".join(parts))

            # ponytail: status is authoritative — the API marks jobs
            # "Completed" even when some variants lack predictions
            # (e.g. 10/15).  The 409 race on /result/ is handled by
            # get_result's retry loop.
            if top_level_status.lower() in ("completed",):
                return responses
            if top_level_status.lower() in ("failed", "error"):
                raise OpenKineticsAPIError(f"OpenKinetics job {job_id} failed: {status_payload}")

            if time.monotonic() - started > timeout_seconds:
                raise OpenKineticsTimeoutError(f"Timed out while waiting for OpenKinetics job {job_id}")
            time.sleep(poll_interval_seconds)

    # -- variant-input normalisation ---------------------------------------

    @staticmethod
    def _normalize_score_variants_input(
        variants: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        """Accept a list of variant dicts and normalise to the internal row
        format.  Each dict must contain a ``protein_sequence`` key."""
        normalized_rows: list[dict[str, str]] = []
        for index, variant in enumerate(variants):
            if not isinstance(variant, dict):
                raise OpenKineticsValidationError("Each variant must be a mapping with a 'protein_sequence' key")

            sequence = variant.get("protein_sequence")
            if not sequence:
                raise OpenKineticsValidationError("Each variant row must include a 'protein_sequence' key")

            normalized_rows.append(
                {
                    "variant_id": str(variant.get("variant_id", f"variant_{index}")),
                    "mutation": str(variant.get("mutation", "")),
                    "protein_sequence": str(sequence),
                }
            )
        if not normalized_rows:
            raise OpenKineticsValidationError("At least one variant row is required")
        return normalized_rows
