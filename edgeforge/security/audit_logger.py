import json
import hashlib
import re
import time
from pathlib import Path
from typing import Dict, Any, List, Mapping, Union

_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class HashableArtifact:
    """Marker base — only subclasses are accepted at the audit seam.

    The seam rejects plain strings, because a string-shaped input gives
    no information about whether the caller intends a path, in-memory
    bytes, or a pre-computed hash. Each subclass represents one of
    those three cases exactly.
    """


class PathRef(HashableArtifact):
    """A file on disk. The audit module streams and hashes it."""

    def __init__(self, path):
        self.path = Path(path)


class RawBytes(HashableArtifact):
    """Bytes already in memory. The audit module hashes them in place."""

    def __init__(self, data):
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("RawBytes requires bytes-like input")
        self.data = bytes(data)


class HashedSha256(HashableArtifact):
    """A 64-character lowercase hex SHA-256, already computed by caller.

    The audit module does not re-hash; it stores this value verbatim.
    Caller takes responsibility for the bytes behind the hash.
    """

    __slots__ = ("digest",)

    def __init__(self, digest: str):
        if not isinstance(digest, str):
            raise TypeError("HashedSha256 requires a hex string")
        digest = digest.strip().lower()
        if not _SHA256_HEX.match(digest):
            raise ValueError(
                f"HashedSha256 must be 64 lowercase hex chars, got {digest!r}"
            )
        self.digest = digest


def hash_artifact(artifact: HashableArtifact) -> HashedSha256:
    """Stream-resolve a HashableArtifact to its 64-hex SHA-256."""
    if isinstance(artifact, HashedSha256):
        return artifact
    if isinstance(artifact, RawBytes):
        return HashedSha256(hashlib.sha256(artifact.data).hexdigest())
    if isinstance(artifact, PathRef):
        h = hashlib.sha256()
        with open(artifact.path, "rb") as fh:
            for block in iter(lambda: fh.read(65536), b""):
                h.update(block)
        return HashedSha256(h.hexdigest())
    raise TypeError(f"unsupported artifact type: {type(artifact).__name__}")


def _validate_artifact(artifact, field: str) -> HashedSha256:
    if isinstance(artifact, str):
        raise TypeError(
            f"{field}: bare strings are not accepted at the audit seam; "
            f"use PathRef, RawBytes, or HashedSha256."
        )
    if not isinstance(artifact, HashableArtifact):
        raise TypeError(
            f"{field}: expected HashableArtifact, got {type(artifact).__name__}"
        )
    return hash_artifact(artifact)


def _resolve_mapping(mapping, field: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for key, value in mapping.items():
        if not isinstance(key, str):
            raise TypeError(f"{field}: keys must be strings, got {type(key).__name__}")
        out[key] = _validate_artifact(value, f"{field}[{key}]").digest
    return out


class AuditLogger:
    def __init__(self, session_id: str, classification: str = "UNCLASSIFIED"):
        self.session_id = session_id
        self.classification = classification
        self.log_entries: List[Dict[str, Any]] = []
        self.chain_hash = hashlib.sha256(
            f"IV_{session_id}".encode()
        ).hexdigest()

    def log_transformation(
        self,
        operation: str,
        inputs: Mapping[str, Union[HashableArtifact, str]],
        outputs: Mapping[str, Union[HashableArtifact, str]],
        metadata: Dict[str, Any],
    ):
        """Logs a single transformation step with cryptographic chaining.

        ``inputs`` and ``outputs`` are mapped name → HashableArtifact.
        The audit module resolves every value to its 64-hex SHA-256
        before chaining.
        """
        if not isinstance(operation, str):
            raise TypeError("operation must be a string")
        input_hashes = _resolve_mapping(inputs, "inputs")
        output_hashes = _resolve_mapping(outputs, "outputs")

        entry: Dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "session_id": self.session_id,
            "sequence": len(self.log_entries),
            "operation": operation,
            "input_hashes": input_hashes,
            "output_hashes": output_hashes,
            "metadata": metadata,
            "classification": self.classification,
            "previous_hash": self.chain_hash,
        }

        entry_hash = hashlib.sha256(
            json.dumps(entry, sort_keys=True).encode()
        ).hexdigest()
        entry["entry_hash"] = entry_hash
        self.chain_hash = entry_hash
        self.log_entries.append(entry)

    def finalize_audit_log(self) -> Dict[str, Any]:
        audit_package = {
            "header": {
                "session_id": self.session_id,
                "start_time": self.log_entries[0]["timestamp"] if self.log_entries else None,
                "end_time": self.log_entries[-1]["timestamp"] if self.log_entries else None,
                "total_operations": len(self.log_entries),
                "final_chain_hash": self.chain_hash,
                "classification": self.classification,
            },
            "entries": self.log_entries,
            "signature": "SIG_SIGNED_WITH_HSM_" + self.chain_hash,
        }
        return audit_package


def verify_audit_integrity(
    audit_package: Dict[str, Any], input_artifact_map: Dict[int, Dict[str, HashableArtifact]] = None
) -> Dict[str, Any]:
    """Verifies chain integrity. If ``input_artifact_map`` is supplied,
    it is keyed by entry sequence and re-hashes each declared PathRef
    to confirm the audit chain still describes the file on disk.
    """
    entries = audit_package["entries"]
    expected_final_hash = audit_package["header"]["final_chain_hash"]

    current_hash = hashlib.sha256(
        f"IV_{audit_package['header']['session_id']}".encode()
    ).hexdigest()

    for i, entry in enumerate(entries):
        if entry["previous_hash"] != current_hash:
            return {
                "valid": False,
                "error": f"CHAIN_TAMPERING_DETECTED_AT_SEQUENCE_{i}",
            }

        if input_artifact_map is not None and i in input_artifact_map:
            declared = entry["input_hashes"]
            for name, artifact in input_artifact_map[i].items():
                expected = hash_artifact(artifact).digest
                recorded = declared.get(name)
                if recorded != expected:
                    return {
                        "valid": False,
                        "error": f"ARTIFACT_TAMPERING_DETECTED_AT_SEQUENCE_{i}_{name}",
                    }

        temp_entry = entry.copy()
        temp_entry.pop("entry_hash", None)
        computed_hash = hashlib.sha256(
            json.dumps(temp_entry, sort_keys=True).encode()
        ).hexdigest()

        if computed_hash != entry.get("entry_hash"):
            return {
                "valid": False,
                "error": f"ENTRY_TAMPERING_DETECTED_AT_SEQUENCE_{i}",
            }

        current_hash = computed_hash

    if current_hash != expected_final_hash:
        return {"valid": False, "error": "FINAL_HASH_MISMATCH"}

    if not audit_package["signature"].endswith(current_hash):
        return {"valid": False, "error": "SIGNATURE_INVALID"}

    return {"valid": True, "operations_verified": len(entries)}
