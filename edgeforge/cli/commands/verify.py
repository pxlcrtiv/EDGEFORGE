import click
import tarfile
import json
import os
import tempfile
from pathlib import Path
from edgeforge.security.audit_logger import verify_audit_integrity, PathRef

# Re-read artifacts only when the manifest authoritatively declares
# their PathRef locations. Plain chain verification runs otherwise.
# Avoids the silent-stem-collision bug a name-guess heuristic would
# introduce.


@click.command()
@click.option("--package", required=True, help="Path to deployment package")
def verify(package):
    """Verify integrity of deployment package and audit trail."""
    click.echo(f"[*] Verifying package: {package}")

    if not os.path.exists(package):
        click.echo(f"[!] File not found: {package}")
        return

    try:
        with tarfile.open(package, "r:gz") as tar:
            manifest_file = tar.extractfile("manifest.json")
            if not manifest_file:
                click.echo("[!] manifest.json missing from package")
                return
            manifest = json.load(manifest_file)

            audit_file = tar.extractfile("security/audit_log.json")
            if not audit_file:
                click.echo("[!] security/audit_log.json missing from package")
                return
            audit_log = json.load(audit_file)

            click.echo(f"[*] Package ID: {manifest['package_id']}")
            click.echo(f"[*] Classification: {manifest['classification']}")
            click.echo(f"[*] Verifying cryptographic audit chain...")

            # Chain-only verification: the chain was the audit log's
            # invariant. Re-reading disk artifacts is opt-in via the
            # manifest's declared artifact_paths table; if that's
            # absent (today's packager doesn't yet emit it), we
            # cannot authoritatively bind filenames to PathRefs.
            artifact_map = None
            declared = manifest.get("artifact_paths")
            if declared:
                artifact_map = {}
                with tempfile.TemporaryDirectory() as extract_dir:
                    tar.extractall(extract_dir, filter="data")
                for entry_idx, paths in declared.items():
                    artifact_map[int(entry_idx)] = {
                        name: PathRef(Path(extract_dir) / p)
                        for name, p in paths.items()
                    }

            v_result = verify_audit_integrity(audit_log, artifact_map)
            if v_result["valid"]:
                click.echo(
                    f"[+] Audit integrity verified. "
                    f"{v_result['operations_verified']} operations confirmed."
                )
                click.echo(
                    f"[+] Final Chain Hash: "
                    f"{audit_log['header']['final_chain_hash']}"
                )
            else:
                click.echo(f"[!] INTEGRITY BREACH: {v_result['error']}")

    except Exception as e:
        click.echo(f"[!] Error during verification: {str(e)}")
