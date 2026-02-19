import pytest
import os
import subprocess

def test_full_pipeline_integration(tmp_path):
    # Use the generate_mock_model script logic to create a model
    import onnx
    from onnx import helper, TensorProto
    
    model_path = tmp_path / "integ_model.onnx"
    X = helper.make_tensor_value_info('X', TensorProto.FLOAT, [1, 1])
    Y = helper.make_tensor_value_info('Y', TensorProto.FLOAT, [1, 1])
    node = helper.make_node('Relu', ['X'], ['Y'])
    graph = helper.make_graph([node], 'integ-test', [X], [Y])
    model = helper.make_model(graph)
    onnx.save(model, str(model_path))
    
    # Run the balance of the pipeline via CLI or direct calls
    # For integration test, direct calls are often safer in restricted envs
    from edgeforge.core.arch_detector import detect_architecture
    from edgeforge.quantization.adaptive_quant import adaptive_quantize
    from edgeforge.hardware.optimizer_factory import optimize_for_hardware
    from edgeforge.security.audit_logger import AuditLogger
    from edgeforge.packaging.air_gap_packager import create_air_gap_package
    
    # 1. Detect
    arch = detect_architecture(str(model_path))
    assert arch['architecture_type'] == 'GENERIC_CNN'
    
    # 2. Quantize
    quant = adaptive_quantize(str(model_path), None, "INT8")
    
    # 3. Optimize (mocked Jetson)
    opt = optimize_for_hardware(quant['quantized_model_path'], "jetson-nano", {"precision": "INT8"})
    
    # 4. Audit & Package
    logger = AuditLogger("INTEG_SESSION")
    logger.log_transformation("integ_op", {"in": "h1"}, {"out": "h2"}, {})
    package = create_air_gap_package(opt['engine_path'], logger.finalize_audit_log(), {"hardware": "jetson-nano", "precision": "INT8"})
    
    assert os.path.exists(package['package_path'])
    
    # Integrity check on package
    from edgeforge.security.audit_logger import verify_audit_integrity
    import tarfile, json
    with tarfile.open(package['package_path'], "r:gz") as tar:
        audit_data = json.load(tar.extractfile("security/audit_log.json"))
        verify_result = verify_audit_integrity(audit_data)
        assert verify_result['valid'] is True
    
    os.remove(package['package_path'])
    if os.path.exists(quant['quantized_model_path']):
        os.remove(quant['quantized_model_path'])
    if os.path.exists(opt['engine_path']):
        os.remove(opt['engine_path'])
