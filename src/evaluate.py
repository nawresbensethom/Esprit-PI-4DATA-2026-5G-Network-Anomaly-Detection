"""
evaluate.py
===========
Evaluation suite for both 6G (anomaly detection) and 5G (classification) models.

6G  – Sections 3.4–3.7, 4.2–4.3, 5, 6.1–6.7
5G  – Blocs 6–12  (metrics table, confusion matrices, ROC/PR, CV, threshold opt.)

Usage
-----
    from evaluate import evaluate_6g, evaluate_5g

    # 6G  (after running train_6g_models)
    evaluate_6g(autoencoder, encoder, iso_forest, splits_dict)

    # 5G  (after running train_5g_models)
    evaluate_5g(models_dict, splits_dict)
"""

import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, average_precision_score,
    confusion_matrix, ConfusionMatrixDisplay,
    roc_curve, precision_recall_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.decomposition import PCA
from sklearn.preprocessing import MinMaxScaler

warnings.filterwarnings('ignore')

SEED = 42


# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _full_metrics(model_name: str, y_true: np.ndarray, y_pred: np.ndarray,
                  anomaly_scores: np.ndarray) -> dict:
    """Compute and print a full evaluation suite; return metrics dict."""
    print('=' * 60)
    print(f'EVALUATION : {model_name}')
    print('=' * 60)

    acc   = accuracy_score(y_true, y_pred)
    prec  = precision_score(y_true, y_pred, zero_division=0)
    rec   = recall_score(y_true, y_pred, zero_division=0)
    f1    = f1_score(y_true, y_pred, zero_division=0)
    try:
        auc_roc = roc_auc_score(y_true, anomaly_scores)
    except Exception:
        auc_roc = float('nan')
    try:
        pr_auc = average_precision_score(y_true, anomaly_scores)
    except Exception:
        pr_auc = float('nan')

    cm  = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)

    print(f'\n  Accuracy    : {acc:.4f}')
    print(f'  Precision   : {prec:.4f}')
    print(f'  Recall      : {rec:.4f}')
    print(f'  F1-score    : {f1:.4f}')
    print(f'  AUC-ROC     : {auc_roc:.4f}')
    print(f'  PR-AUC      : {pr_auc:.4f}')
    print(f'\n  TP={tp}  FP={fp}  FN={fn}  TN={tn}')

    return {
        'Model'     : model_name,
        'Accuracy'  : acc,
        'Precision' : prec,
        'Recall'    : rec,
        'F1-score'  : f1,
        'AUC-ROC'   : auc_roc,
        'PR-AUC'    : pr_auc,
        'TP'        : tp, 'FP': fp, 'FN': fn, 'TN': tn,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 6G  Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def calibrate_threshold(y_val: np.ndarray, scores_val: np.ndarray) -> float:
    """Section 3.6 – F1-optimal threshold on validation set (no test leakage)."""
    precisions, recalls, thresholds = precision_recall_curve(y_val, scores_val)
    f1_scores = (2 * precisions[:-1] * recalls[:-1] /
                 (precisions[:-1] + recalls[:-1] + 1e-8))
    best_idx   = np.argmax(f1_scores)
    threshold  = thresholds[best_idx]

    print(f'  Optimal threshold (F1 on val set) : {threshold:.6f}')
    print(f'  Val  F1={f1_scores[best_idx]:.4f}  '
          f'P={precisions[best_idx]:.4f}  R={recalls[best_idx]:.4f}')
    return float(threshold)


def evaluate_autoencoder(autoencoder, X_val: np.ndarray, y_val: np.ndarray,
                         X_test: np.ndarray, y_test: np.ndarray) -> tuple:
    """Sections 3.4, 3.6, 3.7 – AE reconstruction-error analysis + test evaluation."""
    print('\n' + '=' * 60)
    print('AUTOENCODER — RECONSTRUCTION ERROR ANALYSIS')
    print('=' * 60)

    # Val set errors (threshold calibration)
    X_val_recon  = autoencoder.predict(X_val, verbose=0)
    ae_val_errors = np.mean(np.square(X_val - X_val_recon), axis=1)

    print('\nReconstruction errors on VALIDATION set:')
    print(f'  Benign  — mean MSE : {ae_val_errors[y_val==0].mean():.6f}')
    print(f'  Anomaly — mean MSE : {ae_val_errors[y_val==1].mean():.6f}')

    AE_THRESHOLD = calibrate_threshold(y_val, ae_val_errors)

    # Test set evaluation
    X_test_recon   = autoencoder.predict(X_test, verbose=0)
    ae_test_errors = np.mean(np.square(X_test - X_test_recon), axis=1)
    y_pred_ae      = (ae_test_errors > AE_THRESHOLD).astype(int)

    print('\nReconstruction errors on TEST set:')
    print(f'  Benign  — mean MSE : {ae_test_errors[y_test==0].mean():.6f}')
    print(f'  Anomaly — mean MSE : {ae_test_errors[y_test==1].mean():.6f}')

    scaler_scores = MinMaxScaler()
    ae_test_errors_norm = scaler_scores.fit_transform(
        ae_test_errors.reshape(-1, 1)
    ).flatten()

    return y_pred_ae, ae_test_errors, ae_test_errors_norm, AE_THRESHOLD


def evaluate_isolation_forest(iso_forest, X_test: np.ndarray, y_test: np.ndarray) -> tuple:
    """Sections 4.2–4.3 – IF predictions + score distribution."""
    print('\n' + '=' * 60)
    print('ISOLATION FOREST — TEST PREDICTIONS')
    print('=' * 60)

    # Convention: IF returns +1 (normal) / -1 (anomaly)
    if_raw            = iso_forest.predict(X_test)
    y_pred_if         = np.where(if_raw == 1, 0, 1)
    if_anomaly_scores = -iso_forest.decision_function(X_test)

    scaler_scores     = MinMaxScaler()
    if_scores_norm    = scaler_scores.fit_transform(
        if_anomaly_scores.reshape(-1, 1)
    ).flatten()

    n_detected = y_pred_if.sum()
    print(f'  Anomalies detected: {n_detected} / {len(y_test)} '
          f'({n_detected/len(y_test)*100:.2f}%)')
    return y_pred_if, if_anomaly_scores, if_scores_norm


def plot_reconstruction_errors(ae_val_errors: np.ndarray, y_val: np.ndarray,
                                threshold: float) -> None:
    """Section 3.5 – Error distribution plot."""
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))

    axes[0].hist(ae_val_errors[y_val==0], bins=80, alpha=0.6,
                 color='#2ecc71', label='Benign', density=True)
    axes[0].hist(ae_val_errors[y_val==1], bins=80, alpha=0.6,
                 color='#e74c3c', label='Anomaly', density=True)
    axes[0].axvline(threshold, color='black', linestyle='--', label=f'Threshold={threshold:.4f}')
    axes[0].set_xlabel('Reconstruction Error (MSE)')
    axes[0].set_ylabel('Density')
    axes[0].set_title('AE Reconstruction Error Distribution (Val Set)')
    axes[0].legend()

    axes[1].hist(ae_val_errors, bins=100, color='#3498db', alpha=0.7)
    axes[1].axvline(threshold, color='red', linestyle='--', label=f'Threshold={threshold:.4f}')
    axes[1].set_xlabel('Reconstruction Error (MSE)')
    axes[1].set_title('AE Error Histogram with Threshold')
    axes[1].legend()

    plt.tight_layout()
    plt.savefig('ae_error_distribution.png', dpi=150, bbox_inches='tight')
    plt.show()


def plot_roc_and_pr_6g(y_test: np.ndarray, ae_scores_norm: np.ndarray,
                        if_scores_norm: np.ndarray) -> None:
    """Sections 6.3–6.4 – ROC and PR curves for both 6G models."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))

    # ROC
    for scores, label, color in [
        (ae_scores_norm, 'Autoencoder',      '#3498db'),
        (if_scores_norm, 'Isolation Forest', '#e67e22'),
    ]:
        fpr, tpr, _ = roc_curve(y_test, scores)
        auc         = roc_auc_score(y_test, scores)
        axes[0].plot(fpr, tpr, linewidth=2, color=color,
                     label=f'{label} (AUC={auc:.4f})')
    axes[0].plot([0, 1], [0, 1], 'k--', linewidth=1)
    axes[0].set_xlabel('False Positive Rate')
    axes[0].set_ylabel('True Positive Rate')
    axes[0].set_title('ROC Curves — 6G Models')
    axes[0].legend()

    # PR
    for scores, label, color in [
        (ae_scores_norm, 'Autoencoder',      '#3498db'),
        (if_scores_norm, 'Isolation Forest', '#e67e22'),
    ]:
        prec, rec, _ = precision_recall_curve(y_test, scores)
        pr_auc       = average_precision_score(y_test, scores)
        axes[1].plot(rec, prec, linewidth=2, color=color,
                     label=f'{label} (PR-AUC={pr_auc:.4f})')
    axes[1].set_xlabel('Recall')
    axes[1].set_ylabel('Precision')
    axes[1].set_title('Precision-Recall Curves — 6G Models')
    axes[1].legend()

    plt.tight_layout()
    plt.savefig('roc_pr_6g.png', dpi=150, bbox_inches='tight')
    plt.show()


def plot_latent_space(encoder, X_test: np.ndarray, y_test: np.ndarray) -> None:
    """Section 6.6 – PCA projection of AE latent space."""
    X_encoded = encoder.predict(X_test, verbose=0)
    pca       = PCA(n_components=2, random_state=SEED)
    X_2d      = pca.fit_transform(X_encoded)
    var_exp   = pca.explained_variance_ratio_.sum() * 100

    print(f'PCA variance explained (2D): {var_exp:.1f}%')

    fig, ax = plt.subplots(figsize=(10, 7))
    colors  = {0: '#2ecc71', 1: '#e74c3c'}
    labels  = {0: 'Benign', 1: 'Anomaly'}
    for cls in [0, 1]:
        mask = y_test == cls
        ax.scatter(X_2d[mask, 0], X_2d[mask, 1], c=colors[cls],
                   label=labels[cls], alpha=0.4, s=10)
    ax.set_title(f'Autoencoder Latent Space (PCA) — var={var_exp:.1f}%')
    ax.set_xlabel('PC1'); ax.set_ylabel('PC2'); ax.legend()
    plt.tight_layout()
    plt.savefig('latent_space_6g.png', dpi=150, bbox_inches='tight')
    plt.show()


def plot_if_feature_importance(iso_forest, X_test: np.ndarray,
                                if_scores: np.ndarray, feature_names: list) -> None:
    """Section 6.7 – Feature importance via anomaly-score correlation."""
    correlations = np.abs(np.corrcoef(X_test.T, if_scores)[-1, :-1])
    feat_imp_df  = pd.DataFrame({'Feature': feature_names,
                                  'Abs Correlation': correlations}) \
                     .sort_values('Abs Correlation', ascending=False).head(20)

    fig, ax = plt.subplots(figsize=(10, 7))
    ax.barh(feat_imp_df['Feature'][::-1], feat_imp_df['Abs Correlation'][::-1],
            color='#e67e22')
    ax.set_xlabel('|Correlation with Anomaly Score|')
    ax.set_title('Feature Importance — Isolation Forest (Top 20)')
    plt.tight_layout()
    plt.savefig('if_feature_importance.png', dpi=150, bbox_inches='tight')
    plt.show()


def cross_validate_6g(X_train_normal: np.ndarray, X_all: np.ndarray,
                       y_all: np.ndarray, n_folds: int = 5) -> pd.DataFrame:
    """Section 5 – 5-fold CV stability analysis for Isolation Forest."""
    from sklearn.metrics import f1_score, recall_score, precision_score

    print('=' * 60)
    print(f'SECTION 5 : {n_folds}-FOLD CV STABILITY (Isolation Forest)')
    print('=' * 60)

    skf     = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=SEED)
    results = []

    for fold, (train_idx, test_idx) in enumerate(skf.split(X_all, y_all), 1):
        X_tr, X_te = X_all[train_idx], X_all[test_idx]
        y_tr, y_te = y_all[train_idx], y_all[test_idx]

        X_tr_benign = X_tr[y_tr == 0]
        iso_cv = IsolationForest(n_estimators=100, contamination='auto',
                                  random_state=SEED, n_jobs=-1)
        iso_cv.fit(X_tr_benign)

        preds  = np.where(iso_cv.predict(X_te) == 1, 0, 1)
        scores = -iso_cv.decision_function(X_te)

        results.append({
            'model': 'Isolation Forest',
            'fold':  fold,
            'F1':        f1_score(y_te, preds, zero_division=0),
            'Recall':    recall_score(y_te, preds, zero_division=0),
            'Precision': precision_score(y_te, preds, zero_division=0),
            'AUC_ROC':   roc_auc_score(y_te, scores) if len(np.unique(y_te)) > 1 else float('nan'),
        })
        print(f'  Fold {fold}: F1={results[-1]["F1"]:.4f}  '
              f'Recall={results[-1]["Recall"]:.4f}')

    return pd.DataFrame(results)


def save_6g_models(autoencoder, encoder, iso_forest, ae_threshold: float,
                   models_dir: str = 'saved_models') -> None:
    """Section 7 – Persist all 6G artefacts."""
    import pickle
    os.makedirs(models_dir, exist_ok=True)

    import os
    if_path = os.path.join(models_dir, 'isolation_forest.pkl')
    with open(if_path, 'wb') as f:
        pickle.dump(iso_forest, f)
    print(f'✓ Isolation Forest saved → {if_path}')

    ae_path = os.path.join(models_dir, 'autoencoder.keras')
    autoencoder.save(ae_path)
    print(f'✓ Autoencoder saved      → {ae_path}')

    enc_path = os.path.join(models_dir, 'encoder.keras')
    encoder.save(enc_path)
    print(f'✓ Encoder saved          → {enc_path}')

    thr_path = os.path.join(models_dir, 'ae_threshold.pkl')
    with open(thr_path, 'wb') as f:
        pickle.dump({'threshold': ae_threshold}, f)
    print(f'✓ AE threshold saved     → {thr_path}')


def evaluate_6g(autoencoder, encoder, iso_forest,
                splits_dict: dict, models_dir: str = 'saved_models') -> dict:
    """Full 6G evaluation pipeline.

    Parameters
    ----------
    autoencoder, encoder, iso_forest : trained models
    splits_dict : output of train.train_6g_models (contains X_val_aug, X_test_aug, y_*, ...)

    Returns
    -------
    metrics_dict : {'ae': ..., 'if': ..., 'comparative_df': ...}
    """
    import os
    os.makedirs(models_dir, exist_ok=True)

    X_val   = splits_dict['X_val_aug']
    X_test  = splits_dict['X_test_aug']
    y_val   = splits_dict['y_val_aug']
    y_test  = splits_dict['y_test_aug']

    # ── Autoencoder ──────────────────────────────────────────────────────────
    y_pred_ae, ae_errors, ae_errors_norm, AE_THRESHOLD = evaluate_autoencoder(
        autoencoder, X_val, y_val, X_test, y_test
    )
    plot_reconstruction_errors(ae_errors, y_test, AE_THRESHOLD)
    metrics_ae = _full_metrics('Autoencoder', y_test, y_pred_ae, ae_errors_norm)

    # ── Isolation Forest ─────────────────────────────────────────────────────
    y_pred_if, if_scores, if_scores_norm = evaluate_isolation_forest(
        iso_forest, X_test, y_test
    )
    metrics_if = _full_metrics('Isolation Forest', y_test, y_pred_if, if_scores_norm)

    # ── Comparative plots ────────────────────────────────────────────────────
    plot_roc_and_pr_6g(y_test, ae_errors_norm, if_scores_norm)
    plot_latent_space(encoder, X_test, y_test)
    if 'feature_names' in splits_dict:
        plot_if_feature_importance(iso_forest, X_test, if_scores,
                                   splits_dict['feature_names'])

    # ── Comparative metrics table ────────────────────────────────────────────
    metric_keys  = ['Model', 'Accuracy', 'Precision', 'Recall', 'F1-score', 'AUC-ROC', 'PR-AUC']
    df_metrics   = pd.DataFrame([
        {k: metrics_ae[k] for k in metric_keys},
        {k: metrics_if[k] for k in metric_keys},
    ]).set_index('Model')

    print('\n' + '=' * 65)
    print('COMPARATIVE METRICS TABLE (held-out test set)')
    print('=' * 65)
    print(df_metrics.round(4).to_string())

    # ── Persistence ──────────────────────────────────────────────────────────
    save_6g_models(autoencoder, encoder, iso_forest, AE_THRESHOLD, models_dir)

    return {
        'ae'             : metrics_ae,
        'if'             : metrics_if,
        'comparative_df' : df_metrics,
        'ae_threshold'   : AE_THRESHOLD,
        'y_pred_ae'      : y_pred_ae,
        'y_pred_if'      : y_pred_if,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 5G  Evaluation
# ─────────────────────────────────────────────────────────────────────────────

def _metrics_5g(name: str, y_test: np.ndarray,
                y_pred: np.ndarray, y_proba: np.ndarray) -> dict:
    """Compute metrics for a single 5G model."""
    return {
        'Model'    : name,
        'Accuracy' : accuracy_score(y_test, y_pred),
        'Precision': precision_score(y_test, y_pred, zero_division=0),
        'Recall'   : recall_score(y_test, y_pred, zero_division=0),
        'F1-Score' : f1_score(y_test, y_pred, zero_division=0),
        'ROC-AUC'  : roc_auc_score(y_test, y_proba),
        'PR-AUC'   : average_precision_score(y_test, y_proba),
    }


def plot_confusion_matrices_5g(y_test: np.ndarray,
                                preds: dict, proba: dict) -> None:
    """Bloc 7 – Confusion matrices for all 5G models."""
    n_models = len(preds)
    fig, axes = plt.subplots(1, n_models, figsize=(6 * n_models, 5))
    fig.suptitle('Confusion Matrices — 5G Models', fontsize=13, fontweight='bold')

    for ax, (name, y_pred) in zip(axes, preds.items()):
        cm   = confusion_matrix(y_test, y_pred)
        disp = ConfusionMatrixDisplay(
            confusion_matrix=cm,
            display_labels=['Benign', 'Malicious']
        )
        disp.plot(ax=ax, cmap='Blues', colorbar=False)
        ax.set_title(name)

    plt.tight_layout()
    plt.savefig('confusion_matrices_5g.png', dpi=150, bbox_inches='tight')
    plt.show()


def plot_roc_pr_5g(y_test: np.ndarray, proba: dict) -> None:
    """Bloc 8 – ROC + PR curves."""
    colors = {'Random Forest': 'steelblue', 'XGBoost': 'darkorange',
              'Logistic Regression': 'green'}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    for name, y_proba in proba.items():
        fpr, tpr, _ = roc_curve(y_test, y_proba)
        auc         = roc_auc_score(y_test, y_proba)
        ax1.plot(fpr, tpr, color=colors.get(name, 'gray'),
                 linewidth=2, label=f'{name} (AUC={auc:.4f})')

        prec, rec, _ = precision_recall_curve(y_test, y_proba)
        pr_auc       = average_precision_score(y_test, y_proba)
        ax2.plot(rec, prec, color=colors.get(name, 'gray'),
                 linewidth=2, label=f'{name} (PR-AUC={pr_auc:.4f})')

    ax1.plot([0, 1], [0, 1], 'k--')
    ax1.set_xlabel('False Positive Rate'); ax1.set_ylabel('True Positive Rate')
    ax1.set_title('ROC Curves — 5G Models'); ax1.legend()

    ax2.set_xlabel('Recall'); ax2.set_ylabel('Precision')
    ax2.set_title('PR Curves — 5G Models'); ax2.legend()

    plt.tight_layout()
    plt.savefig('roc_pr_5g.png', dpi=150, bbox_inches='tight')
    plt.show()


def plot_metrics_bar_5g(results_df: pd.DataFrame) -> None:
    """Bloc 9 – Grouped bar chart of all metrics."""
    metrics = ['Accuracy', 'Precision', 'Recall', 'F1-Score', 'ROC-AUC', 'PR-AUC']
    x       = np.arange(len(metrics))
    width   = 0.25
    colors  = ['steelblue', 'darkorange', 'green']

    fig, ax = plt.subplots(figsize=(14, 6))
    for i, (model_name, row) in enumerate(results_df.iterrows()):
        vals = [row[m] for m in metrics]
        ax.bar(x + i * width, vals, width, label=model_name,
               color=colors[i % len(colors)], alpha=0.85)

    ax.set_xticks(x + width)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, 1.1)
    ax.set_title('Model Comparison — All Metrics')
    ax.legend()
    plt.tight_layout()
    plt.savefig('metrics_bar_5g.png', dpi=150, bbox_inches='tight')
    plt.show()


def threshold_optimisation_5g(y_test: np.ndarray, y_proba: np.ndarray,
                                model_name: str) -> float:
    """Bloc 10 – Find F1-optimal threshold for the best 5G model."""
    print('=' * 60)
    print(f'THRESHOLD OPTIMISATION — {model_name}')
    print('=' * 60)

    precisions, recalls, thresholds = precision_recall_curve(y_test, y_proba)
    f1_scores  = (2 * precisions[:-1] * recalls[:-1] /
                  (precisions[:-1] + recalls[:-1] + 1e-8))
    best_idx   = np.argmax(f1_scores)
    best_thr   = thresholds[best_idx]

    print(f'\n  Default threshold (0.5):')
    y_default = (y_proba >= 0.5).astype(int)
    print(f'    F1={f1_score(y_test, y_default):.4f}  '
          f'Recall={recall_score(y_test, y_default):.4f}  '
          f'Precision={precision_score(y_test, y_default):.4f}')

    print(f'\n  Optimal threshold ({best_thr:.4f}):')
    y_optimal = (y_proba >= best_thr).astype(int)
    print(f'    F1={f1_score(y_test, y_optimal):.4f}  '
          f'Recall={recall_score(y_test, y_optimal):.4f}  '
          f'Precision={precision_score(y_test, y_optimal):.4f}')

    return best_thr


def cross_validate_5g(models_dict: dict, X: pd.DataFrame,
                       y: pd.Series, n_folds: int = 5) -> pd.DataFrame:
    """Bloc 11 – Stratified 5-fold CV for all 5G models."""
    print('=' * 60)
    print(f'STRATIFIED {n_folds}-FOLD CROSS-VALIDATION')
    print('=' * 60)

    cv      = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=SEED)
    records = []

    for name, model in [('Random Forest',       models_dict['rf']),
                         ('XGBoost',             models_dict['xgb']),
                         ('Logistic Regression', models_dict['lr'])]:
        f1s   = cross_val_score(model, X, y, cv=cv, scoring='f1',       n_jobs=-1)
        recs  = cross_val_score(model, X, y, cv=cv, scoring='recall',   n_jobs=-1)
        aucs  = cross_val_score(model, X, y, cv=cv, scoring='roc_auc',  n_jobs=-1)
        praus = cross_val_score(model, X, y, cv=cv,
                                scoring='average_precision', n_jobs=-1)

        print(f'\n  {name}:')
        print(f'    F1      : {f1s.mean():.4f} ± {f1s.std():.4f}')
        print(f'    Recall  : {recs.mean():.4f} ± {recs.std():.4f}')
        print(f'    ROC-AUC : {aucs.mean():.4f} ± {aucs.std():.4f}')

        for fold_i, (f1, rec, auc, prauc) in enumerate(zip(f1s, recs, aucs, praus), 1):
            records.append({'Model': name, 'Fold': fold_i,
                             'F1': f1, 'Recall': rec,
                             'ROC-AUC': auc, 'PR-AUC': prauc})

    return pd.DataFrame(records)


def evaluate_5g(models_dict: dict, splits_dict: dict) -> dict:
    """Full 5G evaluation pipeline.

    Parameters
    ----------
    models_dict : {'rf': ..., 'xgb': ..., 'lr': ...}
    splits_dict : output of train.train_5g_models

    Returns
    -------
    results_dict : {'results_df', 'cv_df', 'best_threshold', ...}
    """
    y_test         = splits_dict['y_test']
    rf_pred_proba  = splits_dict['rf_pred_proba']
    xgb_pred_proba = splits_dict['xgb_pred_proba']
    lr_pred_proba  = splits_dict['lr_pred_proba']
    X_train        = splits_dict['X_train']
    X_test         = splits_dict['X_test']
    y_train        = splits_dict['y_train']

    rf_pred  = (rf_pred_proba  >= 0.5).astype(int)
    xgb_pred = (xgb_pred_proba >= 0.5).astype(int)
    lr_pred  = (lr_pred_proba  >= 0.5).astype(int)

    # ── Metrics table (Bloc 6) ───────────────────────────────────────────────
    results = [
        _metrics_5g('Random Forest',       y_test, rf_pred,  rf_pred_proba),
        _metrics_5g('XGBoost',             y_test, xgb_pred, xgb_pred_proba),
        _metrics_5g('Logistic Regression', y_test, lr_pred,  lr_pred_proba),
    ]
    results_df = pd.DataFrame(results).set_index('Model')

    print('\n' + '=' * 62)
    print('COMPARATIVE METRICS TABLE — 5G DATASET')
    print('=' * 62)
    print(results_df.round(4).to_string())

    # ── Plots ────────────────────────────────────────────────────────────────
    preds = {'Random Forest': rf_pred, 'XGBoost': xgb_pred,
             'Logistic Regression': lr_pred}
    proba = {'Random Forest': rf_pred_proba, 'XGBoost': xgb_pred_proba,
             'Logistic Regression': lr_pred_proba}

    plot_confusion_matrices_5g(y_test, preds, proba)
    plot_roc_pr_5g(y_test, proba)
    plot_metrics_bar_5g(results_df)

    # ── Threshold optimisation (best model by F1) ────────────────────────────
    best_model_name = results_df['F1-Score'].idxmax()
    best_proba      = proba[best_model_name]
    best_thr = threshold_optimisation_5g(y_test, best_proba, best_model_name)

    # ── Cross-validation ─────────────────────────────────────────────────────
    X_full = pd.concat([X_train, X_test], axis=0)
    y_full = pd.concat([pd.Series(y_train.values),
                         pd.Series(y_test.values)], axis=0).reset_index(drop=True)
    cv_df  = cross_validate_5g(models_dict, X_full, y_full)

    # ── Critical analysis (Bloc 12) ──────────────────────────────────────────
    best_f1     = results_df['F1-Score'].idxmax()
    best_recall = results_df['Recall'].idxmax()
    best_auc    = results_df['ROC-AUC'].idxmax()
    print(f'\n  Best F1      → {best_f1}')
    print(f'  Best Recall  → {best_recall}')
    print(f'  Best ROC-AUC → {best_auc}')

    return {
        'results_df'     : results_df,
        'cv_df'          : cv_df,
        'best_threshold' : best_thr,
        'best_model'     : best_model_name,
    }
