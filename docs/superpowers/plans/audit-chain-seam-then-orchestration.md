# EDGEFORGE — Deepen the Audit Chain; Then the Pipeline

Carried out of the architecture review on 2026-07-20. Two sequenced, blocking-edge tickets. Each is independently mergeable: the audit-chain fix lands first as a security boundary; the pipeline extraction lands second on top of it.

Vocabulary: **module · interface · implementation · depth · seam · adapter · leverage · locality**. We use these exactly.

---

## Ticket 1 — Collapse the Audit-Chain Seam

**Goal:** The audit chain hashes the artifact, not the path. Anyone reading `audit_log.json` can recompute every artifact's integrity from inside the log.

### Why this is first

EDGEFORGE names "Cryptographic Audit Trail" in its project root. The chain produced today records full filesystem paths under the `input_hashes` key (see `pkg_4cc1c88b/security/audit_log.json:17` — `"input": "/private/tmp/pytest-of-admin/.../model.onnx"`). The chain-of-custody integrity holds across path *strings*. It does **not** establish that the artifact at that path was the one used. A test asserting `input_hashes[*]` values are 64-hex SHA-256 strings would currently fail.

The audit module is fine underneath; the seam around it is wrong. The seam is where to deepen — the implementation already chains correctly.

### Dossier

| Place | Symptom |
|---|---|
| `edgeforge/security/audit_logger.py:6` | `sha256_data(data: str)` over a string — never a path. |
| `edgeforge/security/audit_logger.py:19-40` | `inputs` arg passed through verbatim, hashed into chain. |
| `edgeforge/security/audit_logger.py:71-89` | `verify_audit_integrity` rechecks the chain, *not* the artifacts. |
| `edgeforge/cli/commands/optimize.py:42-49` | Caller passes `{"input": model_path_string}`. |

### Deepening decisions

1. **Tighten the interface.** `log_transformation(*, operation, artifacts: Mapping[str, HashableArtifact], outputs: Mapping[str, HashableArtifact], metadata=None)`. A `HashableArtifact` is one of:
   - `Path` – the audit module streams the file
   - `Raw(bytes)` – already in memory
   - `HashedSha256(str)` – already hashed (caller takes responsibility)
   Anything else → reject with a typed error before the chain advances.

2. **Audit module owns file hashing.** Streaming SHA-256, constant memory regardless of file size. No caller ever computes a hash for the audit module.

3. **CLI becomes a thin caller.** It computes nothing; it just passes `Path(...)` (or `Raw(...)` for in-memory graphs) and lets `AuditLogger` decide what to do with it.

4. **Verifier gains implicit coverage.** When the audit log is verified, every artifact is re-read from disk (or pulled from the manifest's checksum section) and its hash compared to the recorded `inputs`/`outputs` entry. The verifier imports the same `HashableArtifact` parser the logger uses.

### Deletion test

If we delete `AuditLogger.sha256_data` (line 6) and the redundancy with the instance method (line 16), what's left is:
- one chain builder
- one verifier

Both with smaller interfaces and one consistent "artifact = bytes-on-disk" concept. **Complexity concentrates here, vanishes elsewhere.**

### Acceptance tests

| Test | Asserts |
|---|---|
| `test_audit_logger_hashes_file_contents` | `input_hashes["input"]` is a 64-hex SHA-256 string when caller passes `Path(model.onnx)`. |
| `test_audit_logger_rejects_strings_at_seam` | Passing `{"input": "/tmp/foo.onnx"}` raises `TypeError` with a clear message; chain advances zero entries. |
| `test_verify_reads_artifacts_from_disk` | After tamper-with-the-engine-file-on-disk, `verify_audit_integrity` returns `False`. Currently it would return `True`. |
| `test_audit_logger_owns_hashing_no_caller_hashing` | Lint/static: callers do not import `hashlib` and call it themselves before passing to audit. |
| `test_existing_tests_still_pass` | Chain-break, tampering-of-entry tests still pass unchanged. |

### Risks

- **Five `pkg_*/security/audit_log.json` files on disk** are pre-fix and unverifiable. Either delete (preferred) or move to `pkg_legacy/` and ignore.
- **No backfill.** Old logs in the wild stay valid-by-the-old-rule. Document in CHANGELOG.
- **Streaming SHA-256 vs. memory.** Use `hashlib.sha256()` over 64 KB blocks. No memory regression.

### Out of scope

- Replacing the no-op HSM signature string. Tracked separately.
- Restoring `pkg_*` cleanup invariants. Tracked separately.

---

## Ticket 2 — Extract Pipeline; CLI Becomes a Shell

**Goal:** A `Pipeline.run(...)` module owns the orchestration. The Click command parses args and delegates. The iFlow YAML finally matches code. The audit-chain fix from Ticket 1 is the seam the pipeline preserves.

### Why this is second

The Click command `edgeforge/cli/commands/optimize.py` is the only concrete instance of the pipeline. It:
- hardcodes `SESSION_123`
- lazy-imports three other modules inside the function body
- re-loads the model three times across stages
- accepts `--output` but never uses it
- emits click-output lines intermixed with real errors

Once the audit chain is fixed (Ticket 1), every artifact that flows through the pipeline is a `HashableArtifact` already — perfect input for a clean pipeline module.

### Dossier

| Place | Symptom |
|---|---|
| `edgeforge/cli/commands/optimize.py:1-65` | Whole file is the pipeline today. |
| `edgeforge/workflows/iflow/optimize.yaml` | 7 keys disagree with the code (see architecture report §4). |

### Deepening decisions

1. **New module.** `edgeforge/pipeline.py` (or `edgeforge/pipelines/optimization.py` if the team anticipates multiple). One interface: `OptimizationPipeline.run(OptimizationRequest) -> ArtifactBundle`. Pure function over inputs and a returned bundle.

2. **The CLI is a thin shell.** Click is for arg parsing, log routing, exit codes. No orchestration.

3. **Session id becomes a property of the bundle, not a constant.** `uuid4()` per run. The CLI prints it. Tests can inject fixed ids via `OptimizationRequest(session_id=...)`.

4. **Parsed graph passes through.** Load the model once at the top; the `arch_profile` (computed from the graph) flows downstream as data, not a path.

5. **The iFlow YAML is now a faithful description of the pipeline.** Each YAML step corresponds to one method on `OptimizationPipeline` (private or internal seam).

### Deletion test on the CLI

If we delete `commands/optimize.py` but keep the test that asserts the pipeline produces an `ArtifactBundle` — does that test pass? Today, no, because the pipeline is the CLI. After this ticket, yes.

If we then re-create the CLI by writing only arg-parsing code, the original integration test still passes.

### Acceptance tests

| Test | Asserts |
|---|---|
| `test_pipeline_returns_artifact_bundle` | `OptimizationPipeline.run(req)` returns an `ArtifactBundle` with `package_path`, `audit_hash`, `session_id`. |
| `test_pipeline_loads_model_once` | Mock the model-loader; assert it is called exactly one time. |
| `test_pipeline_session_id_default_is_uuid4` | Two consecutive `run` calls produce different ids. |
| `test_pipeline_accepts_injected_session_id` | `OptimizationRequest(session_id="X")` round-trips. |
| `test_cli_is_thin_shell` | Static: `commands/optimize.py` < 25 LOC. |
| `test_iflow_yaml_contract` | Each `iflow/optimize.yaml` step's input keys match the corresponding pipeline method's args. |
| `test_existing_tests_still_pass` | All current tests pass unchanged. |

### Risks

- **Workflow YAML update.** This ticket will rewrite `optimize.yaml` to match code. Coordinate with anyone running iFlow against this repo.
- **Lazy imports removed.** Will surface any circular-import problems hiding behind `optimize.py`. Likely candidates: `audit_logger ↔ pipeline`, `packager ↔ audit`. Solve by protocol types passed through (not module-level imports).

### Out of scope

- Replacing the `deploy.yaml` `transfer` API that doesn't exist. Tracked separately.
- Replacing the `dashboard.py` mock. Tracked separately.

---

## Cross-cutting notes

- **Don't refactor + feature together.** Ticket 1 ships alone; Ticket 2 ships alone. Each on its own clean diff.
- **One commit per acceptance test landing.** Slim commits, easy revert.
- **No coverage regression.** `pytest --cov=edgeforge` baseline established before Ticket 1 starts.

## Sequencing

```
T1.1  Strict interface for HashableArtifact (failing test)
T1.2  AuditLogger accepts HashableArtifact only
T1.3  CLI passes Path / Raw, not paths-as-strings
T1.4  Verifier re-reads artifacts from disk
T1.5  Delete legacy pkg_*/ and document
      ↓ merge
T2.1  OptimizationRequest / ArtifactBundle dataclasses
T2.2  OptimizationPipeline.run loads model once
T2.3  CLI shim over pipeline.run
T2.4  Rewrite iflow/optimize.yaml
      ↓ merge
```

Ticket 2 does not start until Ticket 1 is on `main`.
