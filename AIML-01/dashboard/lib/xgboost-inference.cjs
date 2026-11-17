
"use strict";

const model = require("./xgboost-model.json");

const learner = model.learner;
const booster = learner.gradient_booster.model;
const trees = booster.trees;

const rawBase = learner.learner_model_param.base_score;

const parsedBase = (
  typeof rawBase === "string" && rawBase.trim().startsWith("[")
    ? JSON.parse(rawBase)
    : rawBase
);

const baseProbability = Number(
  Array.isArray(parsedBase) ? parsedBase[0] : parsedBase
);

if (!(baseProbability > 0 && baseProbability < 1)) {
  throw new Error("Unsupported XGBoost base score");
}

if (learner.objective.name !== "binary:logistic") {
  throw new Error("Unsupported XGBoost objective");
}

const baseMargin = Math.log(
  baseProbability / (1 - baseProbability)
);

const featureNames = learner.feature_names;

if (!Array.isArray(featureNames) || featureNames.length !== 23) {
  throw new Error("Unexpected model feature contract");
}

if (trees.some(tree => tree.split_type.some(type => type !== 0))) {
  throw new Error("Categorical trees are unsupported");
}

function predict(row) {
  if (!Array.isArray(row) || row.length !== featureNames.length) {
    throw new Error("Expected exactly 23 ordered model features");
  }

  let margin = baseMargin;

  for (const tree of trees) {
    let node = 0;

    while (tree.left_children[node] !== -1) {
      const index = tree.split_indices[node];
      const threshold = tree.split_conditions[node];
      const value = row[index];

      if (value !== null &&
          (typeof value !== "number" || !Number.isFinite(value))) {
        throw new Error("Invalid feature value");
      }

      const goLeft = value === null
        ? Boolean(tree.default_left[node])
        : Math.fround(value) < threshold;

      node = goLeft
        ? tree.left_children[node]
        : tree.right_children[node];
    }

    margin += tree.split_conditions[node];
  }

  return margin >= 0
    ? 1 / (1 + Math.exp(-margin))
    : Math.exp(margin) / (1 + Math.exp(margin));
}

module.exports = {
  predict,
  featureNames
};
