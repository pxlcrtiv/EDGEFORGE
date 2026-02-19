import pytest
from edgeforge.quantization.adaptive_quant import adaptive_quantize

@pytest.fixture
def mock_model_path(tmp_path):
    # We'll just use a dummy string since adaptive_quantize calls detect_architecture
    # which we already test. For this unit test, we'll assume it handles the mock.
    import onnx
    from onnx import helper, TensorProto
    model_path = tmp_path / "test_quant.onnx"
    X = helper.make_tensor_value_info('X', TensorProto.FLOAT, [1, 1])
    Y = helper.make_tensor_value_info('Y', TensorProto.FLOAT, [1, 1])
    node = helper.make_node('Relu', ['X'], ['Y'])
    graph = helper.make_graph([node], 'test', [X], [Y])
    model = helper.make_model(graph)
    onnx.save(model, str(model_path))
    return str(model_path)

def test_adaptive_quantize_flow(mock_model_path):
    result = adaptive_quantize(mock_model_path, calibration_data=None, target_precision="INT8")
    assert 'quantized_model_path' in result
    assert 'quantization_plan' in result
    assert result['final_accuracy'] >= 0.90
    assert "test_quant_quant.onnx" in result['quantized_model_path']

def test_adaptive_quantize_strategy_selection(mock_model_path):
    result = adaptive_quantize(mock_model_path, None, "INT8")
    plan = result['quantization_plan']
    for layer, details in plan.items():
        assert 'precision' in details
        assert 'reason' in details
