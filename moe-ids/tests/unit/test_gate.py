import numpy as np

from moe_ids.gate import N_EXPERTS, WeightedCombiner, build_gate_model


def test_build_gate_model_compiles() -> None:
    model = build_gate_model(input_dim=16)
    assert model is not None
    assert model.name == "MoE_gate"


def test_gate_model_output_shape() -> None:
    model = build_gate_model(input_dim=16)
    X = np.random.rand(8, 16).astype(np.float32)
    S = np.random.rand(8, N_EXPERTS).astype(np.float32)
    out = model.predict([X, S], verbose=0)
    assert out.shape == (8, 1)


def test_gate_output_in_01() -> None:
    model = build_gate_model(input_dim=16)
    X = np.random.rand(20, 16).astype(np.float32)
    S = np.random.rand(20, N_EXPERTS).astype(np.float32)
    out = model.predict([X, S], verbose=0).ravel()
    assert (out >= 0).all() and (out <= 1).all()


def test_weighted_combiner_output_shape() -> None:
    import tensorflow as tf

    combiner = WeightedCombiner()
    w = tf.constant(np.ones((5, N_EXPERTS), dtype=np.float32) / N_EXPERTS)
    s = tf.constant(np.random.rand(5, N_EXPERTS).astype(np.float32))
    out = combiner([w, s])
    assert out.shape == (5, 1)
