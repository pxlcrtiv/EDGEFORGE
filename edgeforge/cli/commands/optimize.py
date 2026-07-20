import click
from pathlib import Path
from edgeforge.pipeline import OptimizationPipeline, OptimizationRequest


@click.command()
@click.option("--model", required=True, help="Path to input model (.pt, .onnx)")
@click.option("--target", help="Target hardware (jetson-nano, jetson-xavier, xilinx-zynq, generic-arm)")
@click.option("--precision", default="INT8", help="Quantization precision (FP16, INT8, INT4)")
@click.option("--calibration-data", help="Path to calibration dataset (for INT8)")
@click.option("--security-level", default="IL4", help="Target security level (IL4, IL5, IL6)")
def optimize(model, target, precision, calibration_data, security_level):
    """Optimize a model for specified hardware."""
    req = OptimizationRequest(
        model_path=Path(model),
        target=target,
        precision=precision,
        calibration_data=Path(calibration_data) if calibration_data else None,
        security_level=security_level,
    )
    bundle = OptimizationPipeline().run(req)
    click.echo(f"[+] Package created: {bundle.package_path}")
    click.echo(f"[+] Final Chain Hash: {bundle.audit_hash}")
    click.echo("[+] Optimization pipeline finished.")
