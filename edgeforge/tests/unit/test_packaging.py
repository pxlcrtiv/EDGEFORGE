import pytest
import os
import tarfile
from edgeforge.packaging.air_gap_packager import create_air_gap_package

def test_create_air_gap_package(tmp_path):
    # Setup mock optimized model
    model_path = tmp_path / "model.engine"
    model_path.write_bytes(b"MOCK_ENGINE")
    
    # Setup mock audit log
    audit_log = {
        'header': {'end_time': '2025-02-20', 'final_chain_hash': 'h1', 'classification': 'IL5'},
        'entries': [],
        'signature': 'sig1'
    }
    
    target_config = {'hardware': 'jetson', 'precision': 'INT8'}
    
    result = create_air_gap_package(str(model_path), audit_log, target_config)
    
    package_path = result['package_path']
    assert os.path.exists(package_path)
    assert result['checksum'] is not None
    
    # Verify tar content
    with tarfile.open(package_path, "r:gz") as tar:
        names = tar.getnames()
        assert "manifest.json" in names
        assert "model/model.engine" in names
        assert "security/audit_log.json" in names
    
    # Cleanup
    if os.path.exists(package_path):
        os.remove(package_path)
