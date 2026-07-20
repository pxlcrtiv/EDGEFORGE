import click
import tarfile
import json
import os
import tempfile
from pathlib import Path
from edgeforge.security.audit_logger import verify_audit_integrity, PathRef

@click.command()
@click.option("--package", required=True, help="Path to deployment package")
def verify(package):
    """Verify integrity of deployment package and audit trail."""
    click.echo(f"[*] Verifying package: {package}")

    if not os.path.exists(package):
        click.echo(f"[!] File not found: {package}")
        return

    try:
        with tempfile.TemporaryDirectory() as extract_dir:
            with tarfile.open(package, "r:gz") as tar:
                # Extract manifest and audit log to a temp dir so we
                # can pin files onto disk for re-hashing.
                tar.extract("manifest.json", extract_dir, filter="data")
                tar.extract("security/audit_log.json", extract_dir, filter="data")

            manifest_file = Path(extract_dir) / "manifest.json"
            audit_file = Path(extract_dir) / "security" / "audit_log.json"
            with open(manifest_file) as f:
                manifest = json.load(f)
            with open(audit_file) as f:
                audit_log = json.load(f)

            click.echo(f"[*] Package ID: {manifest['package_id']}")
            click.echo(f"[*] Classification: {manifest['classification']}")
            click.echo(f"[*] Verifying cryptographic audit chain...")

            # Build an artifact map from any in-tree files the package
            # re-stages. For each entry that recorded a PathRef,
            # re-hash the corresponding file under the extracted
            # model/ subtree to catch tampering.
            artifact_map = {}
            with tarfile.open(package, "r:gz") as tar:
                tar.extractall(extract_dir, filter="data")
            for i in range(len(audit_log["entries"])):
                artifact_map[i] = {}
            # Map every PathRef in the package layout: model.files.
            model_dir = Path(extract_dir) / "model"
            if model_dir.exists():
                # Index each entry's declared PathRef name against the
                # file at that path inside model/.
                for i, entry in enumerate(audit_log["entries"]):
                    for name in entry.get("input_hashes", {}).keys():
                        # heuristic: try matching by filename
                        for cand in model_dir.iterdir():
                            if cand.is_file() and cand.stem == name:
                                artifact_map[i][name] = PathRef(cand)

            v_result = verify_audit_integrity(audit_log, artifact_map or None)
            if v_result['valid']:
                click.echo(f"[+] Audit integrity verified. {v_result['operations_verified']} operations confirmed.")
                click.echo(f"[+] Final Chain Hash: {audit_log['header']['final_chain_hash']}")
            else:
                click.echo(f"[!] INTEGRITY BREACH: {v_result['error']}")

    except Exception as e:
        click.echo(f"[!] Error during verification: {str(e)}")
