"""XGBoost slice experts and Keras autoencoder protocol experts."""

from __future__ import annotations

import numpy as np
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import BatchNormalization, Dense, Dropout, Input
from tensorflow.keras.models import Model
from tensorflow.keras.optimizers import Adam
from xgboost import XGBClassifier


def train_slice_expert(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    name: str,
    seed: int = 42,
    n_estimators: int = 200,
    max_depth: int = 5,
    learning_rate: float = 0.1,
) -> XGBClassifier:
    """Fit an XGBoost classifier on one 5G slice."""
    neg, pos = (y_tr == 0).sum(), (y_tr == 1).sum()
    scale_pos = max(neg / max(pos, 1), 1e-3)

    clf = XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        scale_pos_weight=scale_pos,
        eval_metric="logloss",
        random_state=seed,
        n_jobs=-1,
        use_label_encoder=False,
    )
    clf.fit(X_tr, y_tr)
    return clf


def build_autoencoder(input_dim: int, bottleneck: int = 6) -> Model:
    inp = Input(shape=(input_dim,), name="input")
    x = Dense(10, activation="relu")(inp)
    x = BatchNormalization()(x)
    x = Dropout(0.2)(x)
    bn = Dense(bottleneck, activation="relu", name="bottleneck")(x)
    x = Dense(10, activation="relu")(bn)
    x = BatchNormalization()(x)
    x = Dropout(0.2)(x)
    out = Dense(input_dim, activation="linear", name="output")(x)
    ae = Model(inp, out, name="Autoencoder")
    ae.compile(optimizer=Adam(1e-3), loss="mse")
    return ae


def train_protocol_autoencoder(
    X_tr: np.ndarray,
    name: str,
    epochs: int = 80,
    batch_size: int = 64,
    bottleneck: int = 6,
) -> Model:
    """Fit a reconstruction autoencoder on one 6G protocol's benign-only data."""
    ae = build_autoencoder(X_tr.shape[1], bottleneck=bottleneck)
    callbacks = [
        EarlyStopping(patience=10, restore_best_weights=True, monitor="val_loss"),
        ReduceLROnPlateau(patience=5, factor=0.5, min_lr=1e-6, monitor="val_loss"),
    ]
    ae.fit(
        X_tr,
        X_tr,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.15,
        callbacks=callbacks,
        verbose=0,
    )
    return ae
