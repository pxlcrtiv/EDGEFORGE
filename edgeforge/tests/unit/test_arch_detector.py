import pytest
import os
from edgeforge.core.arch_detector import detect_architecture

@pytest.fixture
def mock_onnx_model(tmp_path):
    import onnx
    from onnx import helper, TensorProto
    
    model_path = tmp_path / "test_model.onnx"
    X = helper.make_tensor_value_info('X', TensorProto.FLOAT, [1, 3, 224, 224])
    Z = helper.make_tensor_value_info('Z', TensorProto.FLOAT, [1, 16, 224, 224])
    conv_w = helper.make_tensor('conv_w', TensorProto.FLOAT, [16, 3, 3, 3], [0.1]*16*3*3*3)
    
    conv_node = helper.make_node('Conv', ['X', 'conv_w'], ['Y'], kernel_shape=[3, 3], pads=[1, 1, 1, 1])
    add_node = helper.make_node('Add', ['Y', 'Y'], ['Z'])
    
    graph = helper.make_graph([conv_node, add_node], 'test-model', [X], [Z], [conv_w])
    model = helper.make_model(graph, producer_name='edgeforge-test')
    onnx.save(model, str(model_path))
    return str(model_path)

def test_detect_architecture_generic_cnn(mock_onnx_model):
    result = detect_architecture(mock_onnx_model)
    assert 'architecture_type' in result
    assert result['architecture_type'] in ['GENERIC_CNN', 'RESNET_FAMILY'] # ResNet family has skip connections
    assert 'layer_statistics' in result
    assert 'recommended_strategy' in result

def test_detect_architecture_invalid_path():
    with pytest.raises(Exception):
        detect_architecture("non_existent_path.onnx")
