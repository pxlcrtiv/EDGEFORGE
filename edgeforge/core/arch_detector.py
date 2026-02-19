import onnx
import networkx as nx
from typing import Dict, List, Any

def extract_computation_graph(model_path: str) -> nx.DiGraph:
    """Extracts the computation graph from an ONNX model into a NetworkX DiGraph."""
    model = onnx.load(model_path)
    graph = model.graph
    dg = nx.DiGraph()

    # Add nodes for inputs and outputs
    for input_node in graph.input:
        dg.add_node(input_node.name, type="input")
    
    # Add nodes for operators and edges
    for node in graph.node:
        dg.add_node(node.name, type=node.op_type, inputs=list(node.input), outputs=list(node.output))
        for input_name in node.input:
            dg.add_edge(input_name, node.name)
        for output_name in node.output:
            dg.add_edge(node.name, output_name)

    return dg

def count_conv2d_layers(graph: nx.DiGraph) -> int:
    return len([n for n, d in graph.nodes(data=True) if d.get('type') == 'Conv'])

def count_attention_heads(graph: nx.DiGraph) -> int:
    # Transformers often use 'Attention', 'MultiHeadAttention', or specific combinations of MatMul and Softmax
    # This is a simplified heuristic
    return len([n for n, d in graph.nodes(data=True) if d.get('type') in ['Attention', 'MultiHeadAttention']])

def detect_depthwise_conv(graph: nx.DiGraph) -> int:
    # A depthwise conv is a Conv where group = input_channels
    # This info might be in the attributes of the node
    depthwise_count = 0
    # Add logic here to inspect attributes if necessary
    return depthwise_count

def identify_residual_blocks(graph: nx.DiGraph) -> int:
    # Residual blocks typically involve 'Add' operations with a skip connection
    return len([n for n, d in graph.nodes(data=True) if d.get('type') == 'Add'])

def detect_architecture(model_path: str) -> Dict[str, Any]:
    """Identifies model architecture based on graph analysis."""
    graph = extract_computation_graph(model_path)
    
    layer_stats = {
        'conv2d_count': count_conv2d_layers(graph),
        'transformer_blocks': count_attention_heads(graph),
        'depthwise_separable': detect_depthwise_conv(graph),
        'skip_connections': identify_residual_blocks(graph)
    }
    
    if layer_stats['transformer_blocks'] > 0:
        arch_type = 'TRANSFORMER'
        sensitive_layers = [n for n, d in graph.nodes(data=True) if d.get('type') in ['Attention', 'MultiHeadAttention']]
    elif layer_stats['depthwise_separable'] > layer_stats['conv2d_count'] * 0.5:
        arch_type = 'MOBILENET_FAMILY'
        sensitive_layers = [n for n, d in graph.nodes(data=True) if d.get('type') == 'Conv'] # Simplify for now
    elif layer_stats['skip_connections'] > 10:
        arch_type = 'RESNET_FAMILY'
        sensitive_layers = [n for n, d in graph.nodes(data=True) if d.get('type') == 'Add']
    else:
        arch_type = 'GENERIC_CNN'
        sensitive_layers = []
        
    strategy = select_quantization_strategy(arch_type, sensitive_layers)
    
    return {
        'architecture_type': arch_type,
        'layer_statistics': layer_stats,
        'sensitive_layers': sensitive_layers,
        'recommended_strategy': strategy,
        'confidence_score': 0.95 # Mock for now
    }

def select_quantization_strategy(arch_type: str, sensitive_layers: List[str]) -> Dict[str, str]:
    if arch_type == 'TRANSFORMER':
        return {'mode': 'mixed-precision', 'sensitive_layers': 'FP16', 'other': 'INT8'}
    elif arch_type == 'MOBILENET_FAMILY':
        return {'mode': 'FP16', 'reason': 'Depthwise convs are sensitive to INT8'}
    else:
        return {'mode': 'INT8', 'scaling': 'per-channel'}
