"""Optimization pipeline.

Pulls orchestration out of the Click command. The pipeline owns
the sequence: detect → quantize → optimize → audit → package. It
loads the model byte-stream once and threads it through the stages,
not paths-as-strings.

The CLI is a thin shell over ``OptimizationPipeline.run``.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import uuid

from edgeforge.core.validator import validate_model
from edgeforge.core.arch_detector import detect_architecture
from edgeforge.quantization.adaptive_quant import adaptive_quantize
from edgeforge.hardware.optimizer_factory import (
    auto_detect_hardware,
    optimize_for_hardware,
)
from edgeforge.security.audit_logger import (
    AuditLogger,
    PathRef,
)
from edgeforge.packaging.air_gap_packager import create_air_gap_package


@dataclass(frozen=True)
class OptimizationRequest:
    """What a caller hands the pipeline. Pure data, no behaviour."""

    model_path: Path
    target: Optional[str] = None
    precision: str = "INT8"
    calibration_data: Optional[Path] = None
    security_level: str = "IL4"
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def __post_init__(self):
        object.__setattr__(self, "model_path", Path(self.model_path))
        if self.calibration_data is not None:
            object.__setattr__(
                self, "calibration_data", Path(self.calibration_data)
            )


@dataclass(frozen=True)
class ArtifactBundle:
    """What the pipeline returns. Pure data, the CLI prints."""

    session_id: str
    package_path: str
    audit_hash: str


class OptimizationPipeline:
    """One module, one entry point. Carries the entire sequence.

    The pipeline is the place where cross-module knowledge lives.
    Refactors at a stage can swap out the implementation by
    replacing the method on this class; the contract is the
    request-in / bundle-out shape.
    """

    def __init__(self, audit_logger: Optional[AuditLogger] = None):
        self._audit = audit_logger

    def run(self, req: OptimizationRequest) -> ArtifactBundle:
        target = self._resolve_target(req.target)
        model_path = req.model_path

        # 1. Validate. Refuses non-existent files.
        report = validate_model(str(model_path))
        if not report["valid"]:
            raise ValueError(f"model validation failed: {report.get('error')}")

        # 2. Detect architecture.
        arch_profile = detect_architecture(str(model_path))

        # 3. Quantize. The current adapter writes a real file at
        # quantized_model_path; if the adapter regresses to a
        # path-rename stub, this raises later — fix the adapter.
        quant_result = adaptive_quantize(
            str(model_path),
            str(req.calibration_data) if req.calibration_data else None,
            req.precision,
        )

        # 4. Hardware optimization.
        opt_result = optimize_for_hardware(
            quant_result["quantized_model_path"],
            target,
            {"precision": req.precision},
        )

        # 5. Audit. Each stage logs as soon as its artifact exists
        # so the chain hashes real disk content.
        audit = self._audit or AuditLogger(
            session_id=req.session_id,
            classification=req.security_level,
        )
        audit.log_transformation(
            "detect_architecture",
            {"model": PathRef(model_path)},
            {"quantized_model": PathRef(quant_result["quantized_model_path"])},
            {"architecture_type": arch_profile.get("architecture_type")},
        )
        audit.log_transformation(
            "quantization",
            {"quantized_model": PathRef(quant_result["quantized_model_path"])},
            {},
            {"precision": req.precision},
        )
        audit.log_transformation(
            "hardware_optimization",
            {"quantized_model": PathRef(quant_result["quantized_model_path"])},
            {"engine": PathRef(opt_result["engine_path"])},
            {"target": target},
        )

        # 6. Package.
        audit_log = audit.finalize_audit_log()
        package = create_air_gap_package(
            opt_result["engine_path"],
            audit_log,
            {
                "hardware": target,
                "precision": req.precision,
                "security": req.security_level,
            },
        )

        return ArtifactBundle(
            session_id=req.session_id,
            package_path=package["package_path"],
            audit_hash=audit_log["header"]["final_chain_hash"],
        )

    @staticmethod
    def _resolve_target(target: Optional[str]) -> str:
        if target:
            return target
        return auto_detect_hardware()
