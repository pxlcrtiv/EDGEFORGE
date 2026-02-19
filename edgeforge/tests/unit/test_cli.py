import pytest
from click.testing import CliRunner
from edgeforge.cli.main import main
import os

def test_cli_help():
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "EdgeForge" in result.output

def test_cli_optimize_no_args():
    runner = CliRunner()
    result = runner.invoke(main, ["optimize"])
    assert result.exit_code != 0
    assert "Error: Missing option '--model'" in result.output

def test_cli_optimize_mock(tmp_path):
    # Setup mock model
    import onnx
    from onnx import helper, TensorProto
    model_path = tmp_path / "cli_model.onnx"
    X = helper.make_tensor_value_info('X', TensorProto.FLOAT, [1, 1])
    Y = helper.make_tensor_value_info('Y', TensorProto.FLOAT, [1, 1])
    node = helper.make_node('Relu', ['X'], ['Y'])
    graph = helper.make_graph([node], 'cli-test', [X], [Y])
    model = helper.make_model(graph)
    onnx.save(model, str(model_path))
    
    runner = CliRunner()
    # We use --target jetson-nano which is implemented
    result = runner.invoke(main, ["optimize", "--model", str(model_path), "--target", "jetson-nano"])
    assert result.exit_code == 0
    assert "Optimization pipeline finished" in result.output
    
    # Check if a package was created (glob for the filename)
    import glob
    packages = glob.glob("edgeforge_*.il5.tar.gz")
    assert len(packages) >= 1
    
    # Test verify command
    v_result = runner.invoke(main, ["verify", "--package", packages[0]])
    assert v_result.exit_code == 0
    assert "Audit integrity verified" in v_result.output
    
    # Cleanup
    for p in packages:
        os.remove(p)
