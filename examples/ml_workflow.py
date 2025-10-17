#!/usr/bin/env python3
"""
Comprehensive example demonstrating roach Store capabilities.

This script simulates a machine learning workflow with:
- Model training with checkpointing
- Metric logging over iterations
- Multiple experiment runs
- Loading and analysis of saved artifacts
"""

import torch
import torch.nn as nn
from pathlib import Path
import tempfile

from roach.store import Store, iter_stores, store, scratch


def create_simple_model():
    """Create a simple neural network for demonstration."""
    return nn.Sequential(
        nn.Linear(10, 20),
        nn.ReLU(),
        nn.Linear(20, 5),
    )


def simulate_training(store, num_epochs=10, exp_name="default"):
    """Simulate a training run with metric logging."""
    print(f"\n{'='*60}")
    print(f"Training Experiment: {exp_name}")
    print(f"{'='*60}")

    model = create_simple_model()

    # Save initial model
    store.save(model.state_dict(), "initial_model")
    print(f"Saved initial model")

    # Save model config
    config = {
        "learning_rate": 0.001,
        "batch_size": 32,
        "num_epochs": num_epochs,
        "architecture": "simple_mlp",
    }
    store.save(config, "config")
    print(f"Saved config: {config}")

    # Simulate training loop
    for epoch in range(num_epochs):
        # Simulate metrics that improve over time
        loss = 2.0 * (1 - epoch / num_epochs) + torch.rand(1).item() * 0.1
        accuracy = epoch / num_epochs + torch.rand(1).item() * 0.1

        # Log metrics
        store.log("loss", loss)
        store.log("accuracy", accuracy)

        if epoch % 3 == 0:
            print(f"Epoch {epoch}: loss={loss:.4f}, accuracy={accuracy:.4f}")

    # Save final model checkpoint
    store.save(model.state_dict(), "final_model")
    print(f"Saved final model")

    # Save some embeddings
    embeddings = torch.randn(100, 64)
    store.save(embeddings, "embeddings")
    print(f"Saved embeddings of shape {embeddings.shape}")

    # Save results in a subdirectory
    results = {
        "final_loss": loss,
        "final_accuracy": accuracy,
        "converged": True,
    }
    store.save(results, "results/metrics")
    print(f"Saved results in subdirectory")


def analyze_experiment(store):
    """Load and analyze saved experiment data."""
    print(f"\n{'='*60}")
    print(f"Analyzing Experiment: {store.store_id}")
    print(f"{'='*60}")

    # List all stored items
    print("\nStored items:")
    all_items = store.ls("**/*")
    for item in all_items:
        print(f"  - {item}")

    # Load config
    config = store.load("config")
    print(f"\nConfig: {config}")

    # Load and plot metrics
    losses = store.load("loss")
    accuracies = store.load("accuracy")

    print(f"\nTraining metrics:")
    print(f"  Losses: {len(losses)} values")
    print(f"    First 3: {losses[:3].tolist()}")
    print(f"    Last 3: {losses[-3:].tolist()}")
    print(f"  Accuracies: {len(accuracies)} values")
    print(f"    First 3: {accuracies[:3].tolist()}")
    print(f"    Last 3: {accuracies[-3:].tolist()}")

    # Load embeddings
    embeddings = store.load("embeddings")
    print(f"\nEmbeddings shape: {embeddings.shape}")

    # Load results
    results = store.load("results/metrics")
    print(f"\nFinal results: {results}")

    # Load model
    model_state = store.load("final_model")
    print(f"\nModel state dict keys: {list(model_state.keys())}")


def run_multiple_experiments(parent_dir):
    """Run multiple experiments with different configurations."""
    print(f"\n{'#'*60}")
    print("RUNNING MULTIPLE EXPERIMENTS")
    print(f"{'#'*60}")

    experiments = [
        ("baseline", 5),
        ("extended", 10),
        ("long_run", 15),
    ]

    for exp_name, num_epochs in experiments:
        # Create a new store for each experiment
        exp_store = Store()
        exp_store.init(parent=parent_dir, store_id=f"exp_{exp_name}")

        # Run training
        simulate_training(exp_store, num_epochs=num_epochs, exp_name=exp_name)


def compare_experiments(parent_dir):
    """Compare results across multiple experiments."""
    print(f"\n{'#'*60}")
    print("COMPARING ALL EXPERIMENTS")
    print(f"{'#'*60}\n")

    print(f"Parent directory: {parent_dir}")
    print(f"\nFound experiments:")

    for store_id, exp_store in iter_stores(parent_dir):
        print(f"\n  {store_id}:")

        # Load and compare metrics
        losses = exp_store.load("loss")
        accuracies = exp_store.load("accuracy")

        print(f"    Epochs trained: {len(losses)}")
        print(f"    Final loss: {losses[-1].item():.4f}")
        print(f"    Final accuracy: {accuracies[-1].item():.4f}")
        print(f"    Best accuracy: {accuracies.max().item():.4f}")


def demonstrate_global_store():
    """Demonstrate using the global store instance."""
    print(f"\n{'#'*60}")
    print("DEMONSTRATING GLOBAL STORE")
    print(f"{'#'*60}")

    # Initialize global store
    store.init(parent=tempfile.mkdtemp(), store_id="global_experiment")

    # Use global scratch namespace for temporary state
    scratch.iteration = 0
    scratch.best_loss = float('inf')

    print(f"\nUsing global store at: {store.store_dir}")
    print(f"Scratch namespace: iteration={scratch.iteration}, best_loss={scratch.best_loss}")

    # Save some data
    data = torch.randn(5, 5)
    store.save(data, "random_data")

    # Update scratch
    scratch.iteration = 100
    scratch.best_loss = 0.5

    print(f"Updated scratch: iteration={scratch.iteration}, best_loss={scratch.best_loss}")

    # Log some values
    for i in range(5):
        store.log("metric", float(i * 0.1))

    # Load back
    loaded_data = store.load("random_data")
    loaded_metric = store.load("metric")

    print(f"\nLoaded data shape: {loaded_data.shape}")
    print(f"Logged metric values: {loaded_metric.tolist()}")


def main():
    """Main function running all demonstrations."""
    print("="*60)
    print("ROACH STORE COMPREHENSIVE DEMONSTRATION")
    print("="*60)

    # Create temporary directory for experiments
    parent_dir = tempfile.mkdtemp(prefix="roach_demo_")
    print(f"\nUsing temporary directory: {parent_dir}")

    # 1. Run multiple experiments
    run_multiple_experiments(parent_dir)

    # 2. Analyze individual experiments
    for store_id, exp_store in iter_stores(parent_dir):
        analyze_experiment(exp_store)

    # 3. Compare all experiments
    compare_experiments(parent_dir)

    # 4. Demonstrate global store
    demonstrate_global_store()

    print(f"\n{'='*60}")
    print("DEMONSTRATION COMPLETE")
    print(f"{'='*60}")
    print(f"\nExperiment data saved in: {parent_dir}")
    print(f"You can inspect the directory structure and files manually.")


if __name__ == "__main__":
    main()
