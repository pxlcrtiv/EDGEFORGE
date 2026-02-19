import click
import tarfile
import json
import os
from edgeforge.security.audit_logger import verify_audit_integrity

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
            # Extract manifest
            manifest_file = tar.extractfile("manifest.json")
            if not manifest_file:
                click.echo("[!] manifest.json missing from package")
                return
            manifest = json.load(manifest_file)
            
            # Extract audit log
            audit_file = tar.extractfile("security/audit_log.json")
            if not audit_file:
                click.echo("[!] security/audit_log.json missing from package")
                return
            audit_log = json.load(audit_file)
            
            click.echo(f"[*] Package ID: {manifest['package_id']}")
            click.echo(f"[*] Classification: {manifest['classification']}")
            click.echo(f"[*] Verifying cryptographic audit chain...")
            
            v_result = verify_audit_integrity(audit_log)
            if v_result['valid']:
                click.echo(f"[+] Audit integrity verified. {v_result['operations_verified']} operations confirmed.")
                click.echo(f"[+] Final Chain Hash: {audit_log['header']['final_chain_hash']}")
            else:
                click.echo(f"[!] INTEGRITY BREACH: {v_result['error']}")
                
    except Exception as e:
        click.echo(f"[!] Error during verification: {str(e)}")
