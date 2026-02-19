import json
import hashlib
import time
from typing import Dict, Any, List, Optional

def sha256_data(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()

class AuditLogger:
    def __init__(self, session_id: str, classification: str = 'UNCLASSIFIED'):
        self.session_id = session_id
        self.classification = classification
        self.log_entries = []
        self.chain_hash = self.sha256_data(f"IV_{session_id}")
        
    def sha256_data(self, data: str) -> str:
        return hashlib.sha256(data.encode()).hexdigest()
        
    def log_transformation(self, operation: str, inputs: Dict[str, str], outputs: Dict[str, str], metadata: Dict[str, Any]):
        """Logs a single transformation step with cryptographic chaining."""
        entry = {
            'timestamp': time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            'session_id': self.session_id,
            'sequence': len(self.log_entries),
            'operation': operation,
            'input_hashes': inputs, # Expecting already hashed values or short names
            'output_hashes': outputs,
            'metadata': metadata,
            'classification': self.classification,
            'previous_hash': self.chain_hash
        }
        
        # Compute hash of the current entry (excluding itself)
        entry_hash = self.sha256_data(json.dumps(entry, sort_keys=True))
        entry['entry_hash'] = entry_hash
        
        # update chain hash
        self.chain_hash = entry_hash
        
        self.log_entries.append(entry)
        
        # In a real implementation:
        # self.write_to_wal(entry)
        
    def finalize_audit_log(self) -> Dict[str, Any]:
        """Finalizes the audit log and signs it."""
        audit_package = {
            'header': {
                'session_id': self.session_id,
                'start_time': self.log_entries[0]['timestamp'] if self.log_entries else None,
                'end_time': self.log_entries[-1]['timestamp'] if self.log_entries else None,
                'total_operations': len(self.log_entries),
                'final_chain_hash': self.chain_hash,
                'classification': self.classification
            },
            'entries': self.log_entries,
            'signature': "SIG_SIGNED_WITH_HSM_" + self.chain_hash # Mock HSM signature
        }
        return audit_package

def verify_audit_integrity(audit_package: Dict[str, Any]) -> Dict[str, Any]:
    """Verifies the integrity of the entire audit chain."""
    entries = audit_package['entries']
    expected_final_hash = audit_package['header']['final_chain_hash']
    
    current_hash = AuditLogger(audit_package['header']['session_id']).sha256_data(f"IV_{audit_package['header']['session_id']}")
    
    for i, entry in enumerate(entries):
        # Verify previous hash link
        if entry['previous_hash'] != current_hash:
            return {'valid': False, 'error': f'CHAIN_TAMPERING_DETECTED_AT_SEQUENCE_{i}'}
        
        # Recompute entry hash
        temp_entry = entry.copy()
        temp_entry.pop('entry_hash')
        computed_hash = hashlib.sha256(json.dumps(temp_entry, sort_keys=True).encode()).hexdigest()
        
        if computed_hash != entry['entry_hash']:
            return {'valid': False, 'error': f'ENTRY_TAMPERING_DETECTED_AT_SEQUENCE_{i}'}
            
        current_hash = computed_hash
        
    if current_hash != expected_final_hash:
        return {'valid': False, 'error': 'FINAL_HASH_MISMATCH'}
        
    # Verify mock signature
    if not audit_package['signature'].endswith(current_hash):
        return {'valid': False, 'error': 'SIGNATURE_INVALID'}
        
    return {'valid': True, 'operations_verified': len(entries)}
