# AI-Driven Attack Defense for IoT Smart Cities in 6G Networks

## Overview

This project was developed as part of the **PIDATA– 4th Year Engineering Program** at **Esprit School of Engineering – Tunisia** (Academic Year 2025–2026).

The objective of this project is to design an **AI-driven framework for detecting and mitigating cyber-attacks** in IoT-based smart city environments within emerging **6G networks**. The system leverages data analytics and machine learning techniques to identify anomalous network behavior and enhance network security.

---

## Problem Statement

With the rapid growth of IoT devices in smart cities and the evolution toward 6G networks, cybersecurity challenges have become more complex. Traditional rule-based systems are no longer sufficient to detect sophisticated and evolving attacks.

This project addresses:

* Detection of malicious network traffic
* Handling heterogeneous 5G/6G datasets (Global, eMBB, mMTC, URLLC)
* Building intelligent models for real-time anomaly detection

---

## Features

* ✅ Data preprocessing pipeline (cleaning, missing values, encoding)
* ✅ Outlier handling using IQR Winsorization
* ✅ Feature engineering (log transformations, correlation filtering)
* ✅ Categorical encoding (One-Hot Encoding)
* ✅ Multi-dataset analysis (5G traffic scenarios)
* ✅ Machine Learning-based anomaly detection
* ✅ Balanced dataset evaluation and performance metrics

---

## Tech Stack

### Data Processing & Machine Learning

* Python
* Pandas
* NumPy
* Scikit-learn

### Data Visualization

* Matplotlib
* Seaborn

### Optional Extensions

* Streamlit (interactive dashboard)
* Docker (containerization)
* GitHub Actions (CI/CD)

---

## Dataset Description

The project uses multiple datasets representing different 5G traffic scenarios:

* **Global**: Mixed traffic dataset
* **eMBB**: Enhanced Mobile Broadband
* **mMTC**: Massive Machine Type Communications
* **URLLC**: Ultra-Reliable Low Latency Communications

Each dataset includes:

* Network traffic features (packets, bytes, latency, etc.)
* Protocol information
* Target label: **Benign (0) / Malicious (1)**

---

## Data Preprocessing Pipeline

The following steps were applied:

1. Removal of irrelevant features (IDs, constant columns)
2. Handling missing values using **median imputation**
3. Cleaning categorical anomalies (`?` values)
4. Removing highly correlated features
5. Outlier treatment using **IQR-based Winsorization**
6. Log transformation for skewed features
7. One-Hot Encoding for categorical variables
8. Final dataset validation (no missing values, aligned schema)

---

## Machine Learning Approach

### Problem Type

* **Binary Classification** (Benign vs Malicious)

### Models (recommended / used)

* Logistic Regression
* Random Forest
* XGBoost (optional)
* Isolation Forest (for anomaly detection scenario)

### Evaluation Metrics

* Accuracy
* Precision / Recall
* F1-Score
* ROC-AUC
* Confusion Matrix

---

## Results

*(To be updated after training)*

Example:

* Accuracy: XX%
* F1-Score: XX%
* ROC-AUC: XX%

---

## Project Structure

```
📁 project-root
│
├── 📁 data/
│   ├── Global_clean.csv
│   ├── eMBB_clean.csv
│   ├── mMTC_clean.csv
│   └── URLLC_clean.csv
│
├── 📁 notebooks/
│   ├── data_cleaning.ipynb
│   ├── eda.ipynb
│   ├── modeling.ipynb
│
├── 📁 src/
│   ├── preprocessing.py
│   ├── training.py
│   ├── evaluation.py
│
├── 📁 models/
│   └── model.pkl
│
├── requirements.txt
└── README.md
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/your-repo.git
cd your-repo
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the project

* Open notebooks using Jupyter or Google Colab
* Execute preprocessing → modeling → evaluation

---

## Contributors

* Nawres Bensethom
* Bouraoui Rahma
* Cherif Safa
* Mejri Ameni

---

## Academic Context

Developed at **Esprit School of Engineering – Tunisia**
PIDATA – 4th Year Engineering Program
Academic Year: 2025–2026

---

## Future Work

* Integration with real-time streaming data
* Deployment using Streamlit dashboard
* Deep Learning models (LSTM, Autoencoders)
* MLOps pipeline (CI/CD + monitoring)

---

## Acknowledgments

* Esprit School of Engineering
* Academic supervisors and project mentors
* Open-source community
