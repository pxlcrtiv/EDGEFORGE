import click
import os
from pathlib import Path
from edgeforge.core.validator import validate_model, validate_target
from edgeforge.core.arch_detector import detect_architecture
from edgeforge.quantization.adaptive_quant import adaptive_quantize
from edgeforge.hardware.tensorrt_optimizer import TensorRTOptimizer
from edgeforge.security.audit_logger import PathRef, HashableArtifact


def _hash_artifact(path_str: str) -> HashableArtifact:
    """Wrap an in-pipeline path-string as a PathRef for the audit seam.

    Other pipeline stages return paths as strings; the audit seam
    requires a typed HashableArtifact. This helper is the one
    bridge. After the pipeline is extracted to its own module
    (Ticket 2) the helper disappears with the orchestration.
    """
    return PathRef(path_str)


@click.command()
@click.option("--model", required=True, help="Path to input model (.pt, .onnx)")
@click.option("--target", help="Target hardware (jetson-nano, jetson-xavier, xilinx-zynq, generic-arm)")
@click.option("--precision", default="INT8", help="Quantization precision (FP16, INT8, INT4)")
@click.option("--calibration-data", help="Path to calibration dataset (for INT8)")
@click.option("--security-level", default="IL4", help="Target security level (IL4, IL5, IL6)")
@click.option("--output", default="./output", help="Output directory")
def optimize(model, target, precision, calibration_data, security_level, output):
    """Optimize a model for specified hardware."""
    from edgeforge.hardware.optimizer_factory import auto_detect_hardware, optimize_for_hardware
    
    if not target:
        click.echo("[*] No target specified, attempting auto-detection...")
        target = auto_detect_hardware()
        click.echo(f"[*] Detected hardware target: {target}")

    click.echo(f"[*] Validating input model: {model}")
    report = validate_model(model)
    if not report['valid']:
        click.echo(f"[!] Validation failed: {report['error']}")
        return

    # In a real impl, we'd check if target is in supported list from factory
    
    click.echo(f"[*] Detecting architecture for {model}...")
    arch_profile = detect_architecture(model)
    click.echo(f"[*] Architecture detected: {arch_profile['architecture_type']}")
    click.echo(f"[*] Recommended strategy: {arch_profile['recommended_strategy']['mode']}")

    click.echo(f"[*] Starting adaptive quantization (target: {precision})...")
    quant_result = adaptive_quantize(model, calibration_data, precision)
    click.echo(f"[*] Quantization complete. Final accuracy estimate: {quant_result['final_accuracy']}")

    from edgeforge.security.audit_logger import AuditLogger, HashedSha256
    audit = AuditLogger(session_id="SESSION_123", classification=security_level)

    click.echo(f"[*] Optimizing for target {target}...")
    try:
        opt_result = optimize_for_hardware(quant_result['quantized_model_path'], target, {'precision': precision})
        click.echo(f"[*] Hardware optimization complete: {opt_result['engine_path']}")
    except Exception as e:
        click.echo(f"[!] Hardware optimization failed: {str(e)}")
        return

    # One audit entry, post-engine, with both real artifacts. The
    # earlier audit pairs (quant step / hardware step) under the old
    # seam were partly fictitious: the quantizer reported a path it
    # never wrote. The new seam refuses to chain a phantom file, so
    # we collapse to a single honest entry once the engine exists.
    # Ticket 2 will move this into a proper pipeline where every
    # stage logs its own artifact as it materializes.
    audit.log_transformation(
        "optimize_to_engine",
        {"model": PathRef(model), "engine": PathRef(opt_result["engine_path"])},
        {},
        {"precision": precision, "target": target},
    )

    click.echo(f"[*] Generating IL5 air-gap deployment package...")
    from edgeforge.packaging.air_gap_packager import create_air_gap_package
    audit_log = audit.finalize_audit_log()
    package_result = create_air_gap_package(
        opt_result['engine_path'], 
        audit_log, 
        {'hardware': target, 'precision': precision, 'security': security_level}
    )
    
    click.echo(f"[+] Package created: {package_result['package_path']}")
    click.echo(f"[+] Package checksum: {package_result['checksum']}")
    click.echo(f"[+] Optimization pipeline finished. Results in {output}")
