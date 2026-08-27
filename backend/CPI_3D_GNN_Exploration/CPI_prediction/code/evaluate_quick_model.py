
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.nn.functional as F

from sklearn.metrics import (
    roc_auc_score,
    precision_score,
    recall_score,
    accuracy_score,
    f1_score,
    confusion_matrix,
    classification_report
)


class CompoundProteinInteractionPrediction(nn.Module):
    def __init__(self, n_fingerprint, n_word, dim, layer_gnn, window, layer_cnn, layer_output):
        super(CompoundProteinInteractionPrediction, self).__init__()

        self.n_fingerprint = n_fingerprint
        self.n_word = n_word
        self.dim = dim
        self.layer_gnn = layer_gnn
        self.window = window
        self.layer_cnn = layer_cnn
        self.layer_output = layer_output

        self.embed_fingerprint = nn.Embedding(n_fingerprint, dim)
        self.embed_word = nn.Embedding(n_word, dim)

        self.W_gnn = nn.ModuleList([
            nn.Linear(dim, dim) for _ in range(layer_gnn)
        ])

        self.W_cnn = nn.ModuleList([
            nn.Conv2d(
                in_channels=1,
                out_channels=1,
                kernel_size=2 * window + 1,
                stride=1,
                padding=window
            )
            for _ in range(layer_cnn)
        ])

        self.W_attention = nn.Linear(dim, dim)
        self.W_out = nn.ModuleList([
            nn.Linear(2 * dim, 2 * dim) for _ in range(layer_output)
        ])
        self.W_interaction = nn.Linear(2 * dim, 2)

    def gnn(self, xs, A, layer):
        for i in range(layer):
            hs = torch.relu(self.W_gnn[i](xs))
            xs = xs + torch.matmul(A, hs)
        return torch.unsqueeze(torch.mean(xs, 0), 0)

    def attention_cnn(self, x, xs, layer):
        xs = torch.unsqueeze(torch.unsqueeze(xs, 0), 0)

        for i in range(layer):
            xs = torch.relu(self.W_cnn[i](xs))

        xs = torch.squeeze(torch.squeeze(xs, 0), 0)

        h = torch.relu(self.W_attention(x))
        hs = torch.relu(self.W_attention(xs))

        weights = torch.tanh(F.linear(h, hs))
        ys = torch.t(weights) * hs

        return torch.unsqueeze(torch.mean(ys, 0), 0)

    def forward(self, inputs):
        fingerprints, adjacency, words = inputs

        fingerprint_vectors = self.embed_fingerprint(fingerprints)
        compound_vector = self.gnn(fingerprint_vectors, adjacency, self.layer_gnn)

        word_vectors = self.embed_word(words)
        protein_vector = self.attention_cnn(compound_vector, word_vectors, self.layer_cnn)

        cat_vector = torch.cat((compound_vector, protein_vector), 1)

        for j in range(self.layer_output):
            cat_vector = torch.relu(self.W_out[j](cat_vector))

        interaction = self.W_interaction(cat_vector)
        return interaction


def load_tensor(file_name, dtype, device):
    return [
        dtype(d).to(device)
        for d in np.load(file_name + ".npy", allow_pickle=True)
    ]


def load_pickle(file_name):
    with open(file_name, "rb") as f:
        return pickle.load(f)


def shuffle_dataset(dataset, seed):
    np.random.seed(seed)
    np.random.shuffle(dataset)
    return dataset


def split_dataset(dataset, ratio):
    n = int(ratio * len(dataset))
    return dataset[:n], dataset[n:]


def main():
    # Keep these settings aligned with run_training_quick.sh
    DATASET = "human_quick"
    radius = "2"
    ngram = "3"
    dim = 10
    layer_gnn = 1
    window = 11
    layer_cnn = 1
    layer_output = 1

    setting = (
        "human_quick--quick--radius2--ngram3--dim10--layer_gnn1--window11--"
        "layer_cnn1--layer_output1--lr1e-3--lr_decay0.5--decay_interval10--"
        "weight_decay1e-6--iteration3"
    )

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("Evaluation uses device:", device)

    repo_root = Path("..").resolve()

    dir_input = repo_root / "dataset" / DATASET / "input" / f"radius{radius}_ngram{ngram}"
    model_file = repo_root / "output" / "model" / setting

    output_dir = repo_root / "output" / "evaluation"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Input dir:", dir_input)
    print("Model file:", model_file)

    if not model_file.exists():
        raise FileNotFoundError(f"Model file not found: {model_file}")

    compounds = load_tensor(str(dir_input / "compounds"), torch.LongTensor, device)
    adjacencies = load_tensor(str(dir_input / "adjacencies"), torch.FloatTensor, device)
    proteins = load_tensor(str(dir_input / "proteins"), torch.LongTensor, device)
    interactions = load_tensor(str(dir_input / "interactions"), torch.LongTensor, device)

    fingerprint_dict = load_pickle(dir_input / "fingerprint_dict.pickle")
    word_dict = load_pickle(dir_input / "word_dict.pickle")

    n_fingerprint = len(fingerprint_dict)
    n_word = len(word_dict)

    dataset = list(zip(compounds, adjacencies, proteins, interactions))
    dataset = shuffle_dataset(dataset, 1234)

    dataset_train, dataset_temp = split_dataset(dataset, 0.8)
    dataset_dev, dataset_test = split_dataset(dataset_temp, 0.5)

    print("Train/dev/test sizes:", len(dataset_train), len(dataset_dev), len(dataset_test))

    model = CompoundProteinInteractionPrediction(
        n_fingerprint=n_fingerprint,
        n_word=n_word,
        dim=dim,
        layer_gnn=layer_gnn,
        window=window,
        layer_cnn=layer_cnn,
        layer_output=layer_output
    ).to(device)

    model.load_state_dict(torch.load(model_file, map_location=device))
    model.eval()

    y_true = []
    y_pred = []
    y_score = []

    with torch.no_grad():
        for data in dataset_test:
            inputs = data[:-1]
            correct_interaction = data[-1]

            logits = model(inputs)
            probs = F.softmax(logits, dim=1).detach().cpu().numpy()[0]

            pred_label = int(np.argmax(probs))
            true_label = int(correct_interaction.detach().cpu().numpy()[0])
            score = float(probs[1])

            y_true.append(true_label)
            y_pred.append(pred_label)
            y_score.append(score)

    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "auc": roc_auc_score(y_true, y_score) if len(set(y_true)) > 1 else np.nan,
        "n_test": len(y_true),
        "positive_true_count": int(np.sum(y_true)),
        "positive_pred_count": int(np.sum(y_pred)),
    }

    prediction_df = pd.DataFrame({
        "y_true": y_true,
        "y_pred": y_pred,
        "score_interaction": y_score
    })

    cm = confusion_matrix(y_true, y_pred)
    cm_df = pd.DataFrame(
        cm,
        index=["Actual_0_non_interaction", "Actual_1_interaction"],
        columns=["Pred_0_non_interaction", "Pred_1_interaction"]
    )

    report_dict = classification_report(
        y_true,
        y_pred,
        target_names=["non_interaction", "interaction"],
        zero_division=0,
        output_dict=True
    )

    report_df = pd.DataFrame(report_dict).T
    metrics_df = pd.DataFrame([metrics])

    prediction_file = output_dir / "quick_test_predictions.csv"
    cm_file = output_dir / "quick_confusion_matrix.csv"
    report_file = output_dir / "quick_classification_report.csv"
    metrics_file = output_dir / "quick_evaluation_metrics.csv"

    prediction_df.to_csv(prediction_file, index=False)
    cm_df.to_csv(cm_file)
    report_df.to_csv(report_file)
    metrics_df.to_csv(metrics_file, index=False)

    print("\nEvaluation metrics:")
    print(metrics_df)

    print("\nConfusion matrix:")
    print(cm_df)

    print("\nClassification report:")
    print(report_df)

    print("\nSaved files:")
    print(prediction_file)
    print(cm_file)
    print(report_file)
    print(metrics_file)


if __name__ == "__main__":
    main()
