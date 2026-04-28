"""
WeightedCombiner custom Keras layer and gate model builder.
Ported verbatim from Moe.ipynb — no logic changes.
"""

from __future__ import annotations

import tensorflow as tf
import tensorflow.keras.backend as K
from tensorflow.keras.layers import Dense, Dropout, Input, Layer
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam

EXPERT_NAMES: list[str] = ["eMBB", "mMTC", "URLLC", "TCP_AE", "UDP_AE"]
N_EXPERTS: int = len(EXPERT_NAMES)


class WeightedCombiner(Layer):
    """
    Element-wise sum of gate_weights × expert_scores, pushed through a shifted sigmoid.
    Inputs : [gate_weights (n, k), expert_scores (n, k)]
    Output : P(attack) (n, 1)
    The sigmoid smooths the decision and prevents edge saturation.
    """

    def call(self, inputs: list[tf.Tensor]) -> tf.Tensor:  # type: ignore[override]
        w, s = inputs
        combined = K.sum(w * s, axis=1, keepdims=True)
        return K.sigmoid(4.0 * (combined - 0.5))

    def get_config(self) -> dict:
        return super().get_config()


def build_gate_model(input_dim: int, n_experts: int = N_EXPERTS) -> Model:
    """
    Two-input model: unified features (drive the gate) + precomputed expert scores
    (read-only, passed through WeightedCombiner).
    """
    feat_in = Input(shape=(input_dim,), name="unified_features")
    score_in = Input(shape=(n_experts,), name="expert_scores")

    h = Dense(32, activation="relu")(feat_in)
    h = Dropout(0.15)(h)
    h = Dense(16, activation="relu")(h)
    w = Dense(n_experts, activation="softmax", name="gate_weights")(h)

    p = WeightedCombiner(name="combiner")([w, score_in])
    model = Model(inputs=[feat_in, score_in], outputs=p, name="MoE_gate")
    model.compile(optimizer=Adam(1e-3), loss="binary_crossentropy", metrics=["accuracy"])
    return model
