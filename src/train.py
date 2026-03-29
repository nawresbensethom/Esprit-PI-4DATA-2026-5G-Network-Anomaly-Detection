"""
train.py
========
Model training for both datasets.

6G  (unsupervised anomaly detection):
    • Autoencoder  (Keras / TensorFlow)
    • Isolation Forest  (scikit-learn)

5G  (supervised classification):
    • Random Forest
    • XGBoost
    • Logistic Regression

Usage
-----
    from train import train_6g_models, train_5g_models

    # 6G
    ae, iso, splits = train_6g_models('AIoT_6G_CLEANED.csv')

    # 5G
    models, splits  = train_5g_models('Global_CLEANED.csv')
"""

import os
import pickle
import warnings
import time

import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.pipeline import Pipeline

warnings.filterwarnings('ignore')

SEED = 42


# ─────────────────────────────────────────────────────────────────────────────
# 6G  ── Anomaly Detection
# ─────────────────────────────────────────────────────────────────────────────

def load_cleaned_6g(filepath: str) -> tuple:
    """Load the cleaned 6G dataset and return (X, y, feature_names)."""
    print('=' * 60)
    print('DATASET LOADED')
    print('=' * 60)

    df = pd.read_csv(filepath)
    print(f'  Shape    : {df.shape}')
    print(f'  Columns  : {df.shape[1]}  ({df.shape[1]-1} features + Label)')
    print()

    label_counts = df['Label'].value_counts()
    print('Label distribution:')
    print(label_counts)
    print()
    benign_pct = label_counts.get('Benign', 0) / len(df) * 100
    print(f'  Benign   : {benign_pct:.2f}%  →  one-class modelling')

    X = df.drop(columns=['Label']).values.astype(np.float32)
    y = (df['Label'] != 'Benign').astype(int).values
    return X, y, df.drop(columns=['Label']).columns.tolist(), df


def simulate_anomalies(X_benign: np.ndarray, feature_names: list, seed: int = SEED) -> tuple:
    """Section 1.3 – Structured attack-type anomaly injection.

    Returns
    -------
    X_train_normal : 80% benign (for model training)
    X_val_aug      : 10% benign + structured anomalies (threshold calibration)
    X_test_aug     : 10% benign + structured anomalies (final evaluation)
    y_val_aug, y_test_aug : binary labels (0 = benign, 1 = anomaly)
    y_train        : all-zero array (for assertion checks)
    """
    rng = np.random.default_rng(seed)

    # Train / val / test split on benign data
    idx         = np.arange(len(X_benign))
    idx_train, idx_temp = train_test_split(idx, test_size=0.20, random_state=seed)
    idx_val,   idx_test = train_test_split(idx_temp, test_size=0.50, random_state=seed)

    X_train_normal = X_benign[idx_train]
    X_val_benign   = X_benign[idx_val]
    X_test_benign  = X_benign[idx_test]

    n_val  = len(X_val_benign)
    n_test = len(X_test_benign)

    # Attack-type-specific structured perturbations
    def _syn_flood(X_ref, n):
        X_a = X_ref[:n].copy()
        syn_cols = [i for i, f in enumerate(feature_names) if 'SYN' in f.upper()]
        if syn_cols:
            X_a[:, syn_cols] += rng.uniform(3, 8, size=(n, len(syn_cols)))
        return X_a

    def _port_scan(X_ref, n):
        X_a = X_ref[:n].copy()
        dur_cols = [i for i, f in enumerate(feature_names) if 'Duration' in f or 'IAT' in f]
        if dur_cols:
            X_a[:, dur_cols] *= rng.uniform(0.01, 0.1, size=(n, len(dur_cols)))
        return X_a

    def _ddos(X_ref, n):
        X_a = X_ref[:n].copy()
        byte_cols = [i for i, f in enumerate(feature_names) if 'Bytes' in f or 'Packets' in f]
        if byte_cols:
            X_a[:, byte_cols] += rng.uniform(4, 10, size=(n, len(byte_cols)))
        return X_a

    def make_anomalies(X_ref, n_total):
        n_each  = n_total // 3
        X_anom  = np.vstack([
            _syn_flood(X_ref, n_each),
            _port_scan(X_ref, n_each),
            _ddos(X_ref, n_total - 2 * n_each),
        ])
        y_anom  = np.ones(len(X_anom), dtype=int)
        y_ben   = np.zeros(n_total, dtype=int)
        X_aug   = np.vstack([X_ref[:n_total], X_anom])
        y_aug   = np.concatenate([y_ben, y_anom])
        shuffle = rng.permutation(len(X_aug))
        return X_aug[shuffle].astype(np.float32), y_aug[shuffle]

    X_val_aug,  y_val_aug  = make_anomalies(X_val_benign,  n_val)
    X_test_aug, y_test_aug = make_anomalies(X_test_benign, n_test)
    y_train = np.zeros(len(X_train_normal), dtype=int)

    print(f'  Train normal : {X_train_normal.shape}  (100% benign)')
    print(f'  Val aug      : {X_val_aug.shape}   |  anomaly rate {y_val_aug.mean()*100:.1f}%')
    print(f'  Test aug     : {X_test_aug.shape}  |  anomaly rate {y_test_aug.mean()*100:.1f}%')

    return X_train_normal, X_val_aug, X_test_aug, y_val_aug, y_test_aug, y_train


def build_autoencoder(input_dim: int, encoding_dim: int = 8):
    """Section 3.1 – Symmetric encoder-decoder autoencoder."""
    try:
        from tensorflow.keras.models import Model
        from tensorflow.keras.layers import Input, Dense, BatchNormalization, Dropout
    except ImportError:
        raise ImportError('TensorFlow / Keras is required for the Autoencoder. '
                          'Install with: pip install tensorflow')

    inp = Input(shape=(input_dim,), name='Input')

    # Encoder
    x = Dense(32, activation='relu', name='Enc_32')(inp)
    x = BatchNormalization(name='BN_32')(x)
    x = Dropout(0.2)(x)
    x = Dense(16, activation='relu', name='Enc_16')(x)
    x = BatchNormalization(name='BN_16')(x)
    x = Dense(encoding_dim, activation='relu', name='Bottleneck')(x)

    # Decoder
    x = Dense(16, activation='relu', name='Dec_16')(x)
    x = BatchNormalization(name='BN_Dec_16')(x)
    x = Dense(32, activation='relu', name='Dec_32')(x)
    x = BatchNormalization(name='BN_Dec_32')(x)
    out = Dense(input_dim, activation='linear', name='Output')(x)

    autoencoder = Model(inputs=inp, outputs=out, name='Autoencoder')
    encoder     = Model(inputs=inp, outputs=autoencoder.get_layer('Bottleneck').output,
                        name='Encoder')
    autoencoder.compile(optimizer='adam', loss='mse', metrics=['mae'])
    return autoencoder, encoder


def train_autoencoder(autoencoder, X_train: np.ndarray, epochs: int = 100,
                      batch_size: int = 256) -> object:
    """Section 3.2 – Train Autoencoder on benign-only data."""
    try:
        from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    except ImportError:
        raise ImportError('TensorFlow is required.')

    print('=' * 60)
    print('SECTION 3.2 : AUTOENCODER TRAINING')
    print('=' * 60)

    callbacks = [
        EarlyStopping(monitor='val_loss', patience=10,
                      restore_best_weights=True, verbose=1),
        ReduceLROnPlateau(monitor='val_loss', factor=0.5,
                          patience=5, min_lr=1e-6, verbose=1),
    ]

    history = autoencoder.fit(
        X_train, X_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_split=0.15,
        callbacks=callbacks,
        verbose=1,
    )
    return history


def train_isolation_forest(X_train: np.ndarray, seed: int = SEED) -> IsolationForest:
    """Section 4.1 – Train Isolation Forest on 100% benign data."""
    print('=' * 60)
    print('SECTION 4.1 : ISOLATION FOREST — TRAINING')
    print('=' * 60)

    assert (X_train == X_train).all(), 'X_train contains NaN'

    iso_forest = IsolationForest(
        n_estimators=200,
        contamination='auto',
        max_samples='auto',
        random_state=seed,
        n_jobs=-1,
        verbose=0,
    )
    iso_forest.fit(X_train)
    print('  ✓ Isolation Forest fitted.')
    return iso_forest


def train_6g_models(
    cleaned_csv: str,
    ae_epochs: int = 100,
    models_dir: str = 'saved_models',
) -> tuple:
    """Full 6G training pipeline.

    Returns
    -------
    autoencoder, encoder, iso_forest, splits_dict
    """
    os.makedirs(models_dir, exist_ok=True)
    X_all, y_all, feature_names, df = load_cleaned_6g(cleaned_csv)

    # All records are benign in the 6G dataset → use them all for simulation
    X_benign = X_all

    splits = simulate_anomalies(X_benign, feature_names, seed=SEED)
    X_train_normal, X_val_aug, X_test_aug, y_val_aug, y_test_aug, y_train = splits

    # ── Autoencoder ──────────────────────────────────────────────────────────
    INPUT_DIM   = X_train_normal.shape[1]
    autoencoder, encoder = build_autoencoder(INPUT_DIM)
    autoencoder.summary()
    history = train_autoencoder(autoencoder, X_train_normal, epochs=ae_epochs)

    # ── Isolation Forest ─────────────────────────────────────────────────────
    assert y_train.sum() == 0, 'Training set should be 100% benign'
    iso_forest = train_isolation_forest(X_train_normal)

    splits_dict = {
        'X_train_normal' : X_train_normal,
        'X_val_aug'      : X_val_aug,
        'X_test_aug'     : X_test_aug,
        'y_val_aug'      : y_val_aug,
        'y_test_aug'     : y_test_aug,
        'y_train'        : y_train,
        'feature_names'  : feature_names,
    }

    return autoencoder, encoder, iso_forest, history, splits_dict


# ─────────────────────────────────────────────────────────────────────────────
# 5G  ── Supervised Classification
# ─────────────────────────────────────────────────────────────────────────────

def load_cleaned_5g(filepath: str) -> tuple:
    """Bloc 2 – Load cleaned Global dataset and select features."""
    df = pd.read_csv(filepath)
    print(f'Shape : {df.shape}')
    print(f'\nClass distribution:')
    print(df['Label'].value_counts())

    # Drop raw features when log-transformed version exists
    log_cols     = [c for c in df.columns if c.endswith('_log')]
    raw_to_drop  = [c.replace('_log', '') for c in log_cols if c.replace('_log', '') in df.columns]
    df           = df.drop(columns=raw_to_drop)
    print(f'\n  Raw features dropped (log versions present): {raw_to_drop}')

    X = df.drop(columns=['Label'])
    y = (df['Label'] == 'Malicious').astype(int)
    return X, y, df


def train_random_forest(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestClassifier:
    """Bloc 3 – Train Random Forest classifier."""
    print('=' * 58)
    print('         RANDOM FOREST — TRAINING')
    print('=' * 58)

    rf_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',
        random_state=SEED,
        n_jobs=-1,
    )
    start = time.time()
    rf_model.fit(X_train, y_train)
    print(f'  ✓ Random Forest trained in {time.time() - start:.1f}s')
    return rf_model


def train_xgboost(X_train: pd.DataFrame, y_train: pd.Series) -> object:
    """Bloc 4 – Train XGBoost classifier with early stopping on internal val split."""
    print('=' * 58)
    print('         XGBOOST — TRAINING')
    print('=' * 58)

    try:
        from xgboost import XGBClassifier
    except ImportError:
        raise ImportError('xgboost is required: pip install xgboost')

    X_tr, X_val, y_tr, y_val = train_test_split(
        X_train, y_train, test_size=0.1, random_state=SEED, stratify=y_train
    )

    neg  = (y_tr == 0).sum()
    pos  = (y_tr == 1).sum()
    spw  = neg / pos if pos > 0 else 1

    xgb_model = XGBClassifier(
        n_estimators=500,
        learning_rate=0.05,
        max_depth=6,
        subsample=0.8,
        colsample_bytree=0.8,
        scale_pos_weight=spw,
        early_stopping_rounds=20,
        eval_metric='logloss',
        use_label_encoder=False,
        random_state=SEED,
        n_jobs=-1,
        verbosity=0,
    )

    start = time.time()
    xgb_model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)
    print(f'  ✓ XGBoost trained in {time.time() - start:.1f}s')
    print(f'  Best iteration: {xgb_model.best_iteration}')
    return xgb_model


def train_logistic_regression(X_train: pd.DataFrame, y_train: pd.Series) -> Pipeline:
    """Bloc 5 – Logistic Regression inside a Pipeline (scaler + LR)."""
    print('=' * 58)
    print('         LOGISTIC REGRESSION — TRAINING')
    print('=' * 58)

    lr_pipeline = Pipeline([
        ('scaler', StandardScaler()),
        ('lr', LogisticRegression(
            max_iter=1000,
            class_weight='balanced',
            solver='lbfgs',
            random_state=SEED,
        ))
    ])

    start = time.time()
    lr_pipeline.fit(X_train, y_train)
    print(f'  ✓ Logistic Regression trained in {time.time() - start:.1f}s')
    return lr_pipeline


def save_5g_models(rf_model, xgb_model, lr_pipeline, output_dir: str = '.') -> None:
    """Bloc 13 – Persist all 5G models to disk."""
    try:
        import joblib
    except ImportError:
        import pickle as joblib

    joblib.dump(rf_model,    os.path.join(output_dir, 'model_random_forest.pkl'))
    joblib.dump(xgb_model,   os.path.join(output_dir, 'model_xgboost.pkl'))
    joblib.dump(lr_pipeline, os.path.join(output_dir, 'model_logistic_regression.pkl'))
    joblib.dump(lr_pipeline.named_steps['scaler'],
                os.path.join(output_dir, 'scaler_logistic_regression.pkl'))

    print('✓ Models saved:')
    for f in ['model_random_forest.pkl', 'model_xgboost.pkl',
              'model_logistic_regression.pkl', 'scaler_logistic_regression.pkl']:
        path = os.path.join(output_dir, f)
        if os.path.exists(path):
            print(f'  {path}  ({os.path.getsize(path)/1e3:.1f} KB)')


def train_5g_models(
    cleaned_csv: str = 'Global_CLEANED.csv',
    test_size: float = 0.20,
    output_dir: str = '.',
) -> tuple:
    """Full 5G training pipeline.

    Returns
    -------
    models_dict : {'rf': rf_model, 'xgb': xgb_model, 'lr': lr_pipeline}
    splits_dict : {'X_train', 'X_test', 'y_train', 'y_test',
                   'rf_pred_proba', 'xgb_pred_proba', 'lr_pred_proba'}
    """
    X, y, df = load_cleaned_5g(cleaned_csv)

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=SEED, stratify=y
    )
    print(f'\n  Train : {X_train.shape}  |  Test : {X_test.shape}')
    print(f'  Train positive rate : {y_train.mean()*100:.2f}%')
    print(f'  Test  positive rate : {y_test.mean()*100:.2f}%')

    rf_model   = train_random_forest(X_train, y_train)
    xgb_model  = train_xgboost(X_train, y_train)
    lr_pipeline = train_logistic_regression(X_train, y_train)

    # Predict probabilities for evaluation
    rf_pred_proba  = rf_model.predict_proba(X_test)[:, 1]
    xgb_pred_proba = xgb_model.predict_proba(X_test)[:, 1]
    lr_pred_proba  = lr_pipeline.predict_proba(X_test)[:, 1]

    save_5g_models(rf_model, xgb_model, lr_pipeline, output_dir)

    models_dict = {
        'rf'  : rf_model,
        'xgb' : xgb_model,
        'lr'  : lr_pipeline,
    }
    splits_dict = {
        'X_train'        : X_train,
        'X_test'         : X_test,
        'y_train'        : y_train,
        'y_test'         : y_test,
        'rf_pred_proba'  : rf_pred_proba,
        'xgb_pred_proba' : xgb_pred_proba,
        'lr_pred_proba'  : lr_pred_proba,
    }
    return models_dict, splits_dict
