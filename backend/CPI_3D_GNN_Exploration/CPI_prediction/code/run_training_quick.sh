#!/bin/bash

DATASET=human_quick

radius=2
ngram=3
dim=10

layer_gnn=1
side=5
window=$((2*side+1))
layer_cnn=1
layer_output=1

lr=1e-3
lr_decay=0.5
decay_interval=10
weight_decay=1e-6

# Quick smoke test only.
# iteration=3 means it will run epochs 1 and 2 because run_training.py uses range(1, iteration).
iteration=3

setting=$DATASET--quick--radius$radius--ngram$ngram--dim$dim--layer_gnn$layer_gnn--window$window--layer_cnn$layer_cnn--layer_output$layer_output--lr$lr--lr_decay$lr_decay--decay_interval$decay_interval--weight_decay$weight_decay--iteration$iteration

python run_training.py $DATASET $radius $ngram $dim $layer_gnn $window $layer_cnn $layer_output $lr $lr_decay $decay_interval $weight_decay $iteration $setting
