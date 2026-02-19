from abc import ABC, abstractmethod
from typing import Dict, Any

class BaseOptimizer(ABC):
    """Abstract base class for hardware-specific optimizers."""
    
    @abstractmethod
    def optimize(self, model_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Optimizes a model for the target hardware."""
        pass
