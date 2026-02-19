from typing import Dict, Any
from edgeforge.hardware.tensorrt_optimizer import TensorRTOptimizer
from edgeforge.hardware.vitis_optimizer import VitisAIOptimizer
from edgeforge.hardware.onnx_optimizer import ONNXOptimizer

def optimize_for_hardware(model_path: str, target: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """Routes the optimization request to the correct hardware backend."""
    
    if target.startswith('jetson'):
        optimizer = TensorRTOptimizer()
    elif target.startswith('xilinx'):
        optimizer = VitisAIOptimizer()
    elif target == 'generic-arm':
        optimizer = ONNXOptimizer()
    else:
        raise ValueError(f"Unsupported hardware target: {target}")
        
    return optimizer.optimize(model_path, config)

def auto_detect_hardware() -> str:
    """Detects available hardware on the host system."""
    # Simplified mock detection
    import platform
    machine = platform.machine()
    
    if machine == 'aarch64':
        # Check for NVIDIA Tegra files to distinguish Jetson
        if os.path.exists('/sys/module/tegra_fuse'):
            return 'jetson-xavier'
        return 'generic-arm'
    elif machine == 'x86_64':
        # Check for Xilinx devices if PCIe available
        return 'x86-cpu' # placeholder
    return 'unknown'
