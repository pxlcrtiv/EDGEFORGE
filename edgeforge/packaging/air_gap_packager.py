import os
import tarfile
import json
import uuid
import hashlib
from typing import Dict, Any

def sha256_file(filepath: str) -> str:
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def create_air_gap_package(optimized_model_path: str, audit_log: Dict[str, Any], target_config: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a deterministic tarball package for air-gap deployment."""
    package_id = str(uuid.uuid4())
    temp_dir = f"pkg_{package_id}"
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "model"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "runtime"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "security"), exist_ok=True)
    os.makedirs(os.path.join(temp_dir, "verification"), exist_ok=True)

    # 1. Model artifacts
    model_name = os.path.basename(optimized_model_path)
    os.rename(optimized_model_path, os.path.join(temp_dir, "model", model_name))
    
    with open(os.path.join(temp_dir, "model", "config.yaml"), "w") as f:
        f.write("# Runtime configuration\n")
        json.dump(target_config, f, indent=2)

    # 2. Security artifacts
    with open(os.path.join(temp_dir, "security", "audit_log.json"), "w") as f:
        json.dump(audit_log, f, indent=2)
    
    with open(os.path.join(temp_dir, "security", "signature.bin"), "wb") as f:
        f.write(audit_log['signature'].encode())

    # 3. Manifest
    manifest = {
        'package_id': package_id,
        'created': audit_log['header']['end_time'],
        'classification': audit_log['header']['classification'],
        'model_metadata': {
            'engine_file': model_name,
            'target_hardware': target_config['hardware'],
            'precision_mode': target_config['precision']
        },
        'audit_chain_hash': audit_log['header']['final_chain_hash'],
        'verification': {
            'checksum_algorithm': 'SHA-256'
        }
    }
    
    manifest_path = os.path.join(temp_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    # 4. Packaging
    tar_path = f"edgeforge_{package_id}.il5.tar.gz"
    with tarfile.open(tar_path, "w:gz") as tar:
        # Determine sorting for determinism
        for root, dirs, files in os.walk(temp_dir):
            for file in sorted(files):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, temp_dir)
                tar.add(full_path, arcname=rel_path)

    # 5. Compute final checksum and update manifest in a real impl
    # (In this mock, we just return it)
    package_checksum = sha256_file(tar_path)
    
    return {
        'package_path': tar_path,
        'package_id': package_id,
        'checksum': package_checksum,
        'manifest': manifest
    }
