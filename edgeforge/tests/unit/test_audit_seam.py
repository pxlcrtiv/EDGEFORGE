"""Tests for the audit-chain artifact seam.

The audit logger accepts a HashableArtifact at its seam, so callers
cannot pass strings that look like paths. Strings are only allowed as
'HashedSha256' type — a deliberate, typed represent-as-already-hashed.
Files are hashed by the audit module itself; callers do not import
hashlib.
"""
import re
import hashlib
from pathlib import Path

import pytest

from edgeforge.security.audit_logger import (
    AuditLogger,
    HashedSha256,
    HashableArtifact,
    PathRef,
    RawBytes,
)


def test_hashable_artifact_rejects_plain_string():
    """Passing a bare string as an artifact raises at the seam."""
    logger = AuditLogger(session_id="SEAM_TEST")
    with pytest.raises(TypeError):
        logger.log_transformation(
            "quantization",
            {"input": "/tmp/model.onnx"},
            {"output": HashedSha256("a" * 64)},
            {},
        )


def test_hashable_artifact_hashes_file_contents(tmp_path):
    """A PathRef is streamed and hashed by the audit module."""
    model = tmp_path / "model.onnx"
    payload = b"some real model bytes"
    model.write_bytes(payload)

    expected_hash = hashlib.sha256(payload).hexdigest()
    assert re.fullmatch(r"[0-9a-f]{64}", expected_hash)

    logger = AuditLogger(session_id="FILE_HASH_TEST")
    logger.log_transformation(
        "quantization",
        {"input": PathRef(model)},
        {"output": HashedSha256(expected_hash)},
        {},
    )

    package = logger.finalize_audit_log()
    recorded = package["entries"][0]["input_hashes"]["input"]
    assert recorded == expected_hash
    assert recorded != str(model)


def test_hashable_artifact_accepts_raw_bytes():
    """Raw bytes are hashed in memory."""
    payload = b"in-memory graph"
    logger = AuditLogger(session_id="RAW_TEST")
    logger.log_transformation(
        "optimization",
        {"graph": RawBytes(payload)},
        {"engine": HashedSha256("b" * 64)},
        {},
    )
    package = logger.finalize_audit_log()
    expected = hashlib.sha256(payload).hexdigest()
    assert package["entries"][0]["input_hashes"]["graph"] == expected


def test_hashable_artifact_already_hashed_kept_verbatim():
    """HashedSha256 is pass-through — caller takes responsibility."""
    logger = AuditLogger(session_id="PRE_HASHED_TEST")
    h = "c" * 64
    logger.log_transformation(
        "x",
        {"input": HashedSha256(h)},
        {"output": HashedSha256("d" * 64)},
        {},
    )
    package = logger.finalize_audit_log()
    assert package["entries"][0]["input_hashes"]["input"] == h


def test_verify_passes_when_artifacts_intact(tmp_path):
    """verify_audit_integrity re-reads PathRef inputs and confirms
    their hashes still match. Tampering the engine file after a run
    must be detected.
    """
    from edgeforge.security.audit_logger import verify_audit_integrity

    model = tmp_path / "model.onnx"
    model.write_bytes(b"original-payload")

    logger = AuditLogger(session_id="VERIFY_TEST", classification="IL5")
    logger.log_transformation(
        "optimize",
        {"model": PathRef(model)},
        {},
        {},
    )
    package = logger.finalize_audit_log()

    # Sanity: without an artifact map, verify still passes (legacy
    # behaviour — chain-only).
    assert verify_audit_integrity(package)["valid"] is True

    # With the artifact map: re-read the file, hash it, compare.
    artifact_map = {0: {"model": PathRef(model)}}
    result = verify_audit_integrity(package, artifact_map)
    assert result["valid"] is True


def test_verify_detects_engine_file_tampering(tmp_path):
    """If the engine (or any PathRef input) is swapped after the run,
    verify_audit_integrity must catch it via re-read.
    """
    from edgeforge.security.audit_logger import verify_audit_integrity

    engine = tmp_path / "model.engine"
    engine.write_bytes(b"original-engine-bytes")

    logger = AuditLogger(session_id="TAMPER_ENGINE")
    logger.log_transformation(
        "optimize",
        {"engine": PathRef(engine)},
        {},
        {},
    )
    package = logger.finalize_audit_log()

    # Tamper.
    engine.write_bytes(b"attacker-bytes")

    artifact_map = {0: {"engine": PathRef(engine)}}
    result = verify_audit_integrity(package, artifact_map)
    assert result["valid"] is False
    assert "ARTIFACT_TAMPERING" in result["error"]
