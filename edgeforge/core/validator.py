import os
from typing import Dict, Any, List

def validate_model(model_path: str) -> Dict[str, Any]:
    """Validates the input model file and returns a report."""
    if not os.path.exists(model_path):
        return {'valid': False, 'error': f"File {model_path} does not exist"}
    
    size_mb = os.path.getsize(model_path) / (1024 * 1024)
    
    return {
        'valid': True,
        'path': model_path,
        'size_mb': size_mb,
        'format': os.path.splitext(model_path)[1][1:].upper()
    }

def validate_target(target: str) -> bool:
    """Validates if the target hardware is supported."""
    supported_targets = ['jetson-nano', 'jetson-xavier', 'jetson-orin', 'xilinx-zynq']
    return target in supported_targets
