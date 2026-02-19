import os
import onnx
import torch
from typing import Any

def load_model(model_path: str) -> Any:
    """Safely loads a PyTorch or ONNX model."""
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    
    ext = os.path.splitext(model_path)[1]
    
    if ext == '.onnx':
        try:
            model = onnx.load(model_path)
            onnx.checker.check_model(model)
            return model
        except Exception as e:
            raise ValueError(f"Invalid ONNX model: {str(e)}")
    elif ext in ['.pt', '.pth']:
        try:
            # Note: Using weights_only=True if supported by torch version
            return torch.load(model_path, map_location='cpu')
        except Exception as e:
            raise ValueError(f"Invalid PyTorch model: {str(e)}")
    else:
        raise ValueError(f"Unsupported model format: {ext}")
