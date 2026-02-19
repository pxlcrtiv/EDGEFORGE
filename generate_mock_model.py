import onnx
from onnx import helper
from onnx import TensorProto

def create_minimal_onnx(model_path: str):
    # Create input (value_info)
    X = helper.make_tensor_value_info('X', TensorProto.FLOAT, [1, 3, 224, 224])
    
    # Create nodes
    # Conv node
    conv_w = helper.make_tensor('conv_w', TensorProto.FLOAT, [16, 3, 3, 3], [0.1]*16*3*3*3)
    conv_node = helper.make_node(
        'Conv',
        ['X', 'conv_w'],
        ['Y'],
        kernel_shape=[3, 3],
        pads=[1, 1, 1, 1]
    )
    
    # Add node (Skip connection mock)
    # We need a compatible tensor for Add. Let's just Add Y to itself for simplicity in this mock
    add_node = helper.make_node(
        'Add',
        ['Y', 'Y'],
        ['Z']
    )
    
    # Create output
    Z = helper.make_tensor_value_info('Z', TensorProto.FLOAT, [1, 16, 224, 224])
    
    # Create graph
    graph = helper.make_graph(
        [conv_node, add_node],
        'test-model',
        [X],
        [Z],
        [conv_w]
    )
    
    # Create model
    model = helper.make_model(graph, producer_name='edgeforge-test')
    
    onnx.save(model, model_path)
    print(f"Mock model saved to {model_path}")

if __name__ == "__main__":
    create_minimal_onnx("test_model.onnx")
