#!/usr/bin/env python3
"""
Comprehensive example demonstrating roach plotting capabilities.

This script demonstrates:
- Publication-quality plot setup
- Training curve visualization
- Multi-experiment comparison plots
- Figure saving with proper sizing
- LaTeX table generation
"""

import tempfile
from pathlib import Path
import torch
import numpy as np
from matplotlib import pyplot as plt

from roach.paper import setup_plt, save_fig, save_tex, LINE
from roach.store import Store


def generate_sample_data():
    """Generate sample training data for multiple experiments."""
    experiments = {}

    configs = {
        "baseline": {"lr": 0.001, "epochs": 50},
        "high_lr": {"lr": 0.01, "epochs": 50},
        "long_train": {"lr": 0.001, "epochs": 100},
    }

    for name, config in configs.items():
        epochs = config["epochs"]
        lr = config["lr"]

        # Generate synthetic loss curves
        x = np.linspace(0, epochs, epochs)
        base_loss = 2.0 * np.exp(-x / (epochs * 0.3))
        noise = np.random.randn(epochs) * 0.1 * (1 + lr * 5)
        loss = base_loss + noise

        # Generate synthetic accuracy curves
        base_acc = 1 - np.exp(-x / (epochs * 0.25))
        noise = np.random.randn(epochs) * 0.05
        accuracy = base_acc + noise

        experiments[name] = {
            "loss": torch.tensor(loss),
            "accuracy": torch.tensor(accuracy),
            "config": config,
        }

    return experiments


def demo_basic_plot(output_dir):
    """Demonstrate basic single-experiment plot."""
    print("\n" + "="*60)
    print("DEMO 1: Basic Training Curve")
    print("="*60)

    setup_plt()

    # Generate data
    epochs = 50
    x = np.arange(epochs)
    loss = 2.0 * np.exp(-x / 15) + np.random.randn(epochs) * 0.1

    # Create figure
    fig, ax = plt.subplots(figsize=(LINE, LINE * 0.6))
    ax.plot(x, loss, linewidth=1.5)
    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.set_title("Training Loss Over Time")
    ax.grid(True, alpha=0.3)

    # Save figure
    save_path = f"{output_dir}/basic_training_curve.pdf"
    save_fig(fig, save_path)
    plt.close(fig)


def demo_multi_experiment_plot(output_dir, experiments):
    """Demonstrate comparing multiple experiments."""
    print("\n" + "="*60)
    print("DEMO 2: Multi-Experiment Comparison")
    print("="*60)

    setup_plt()

    # Create figure with two subplots
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(LINE, LINE * 0.45))

    colors = plt.cm.tab10(np.linspace(0, 1, len(experiments)))

    # Plot losses
    for (name, data), color in zip(experiments.items(), colors):
        loss = data["loss"]
        epochs = len(loss)
        x = np.arange(epochs)
        ax1.plot(x, loss, label=name, linewidth=1.5, color=color, alpha=0.8)

    ax1.set_xlabel("Epoch")
    ax1.set_ylabel("Loss")
    ax1.set_title("Training Loss")
    ax1.legend(fontsize=6)
    ax1.grid(True, alpha=0.3)

    # Plot accuracies
    for (name, data), color in zip(experiments.items(), colors):
        accuracy = data["accuracy"]
        epochs = len(accuracy)
        x = np.arange(epochs)
        ax2.plot(x, accuracy, label=name, linewidth=1.5, color=color, alpha=0.8)

    ax2.set_xlabel("Epoch")
    ax2.set_ylabel("Accuracy")
    ax2.set_title("Validation Accuracy")
    ax2.legend(fontsize=6)
    ax2.grid(True, alpha=0.3)

    # Save figure
    save_path = f"{output_dir}/multi_experiment_comparison.pdf"
    save_fig(fig, save_path)
    plt.close(fig)


def demo_advanced_plot(output_dir):
    """Demonstrate advanced plotting with error bars."""
    print("\n" + "="*60)
    print("DEMO 3: Advanced Plot with Error Bars")
    print("="*60)

    setup_plt()

    # Generate data with multiple runs
    epochs = 30
    num_runs = 5
    x = np.arange(epochs)

    all_losses = []
    for _ in range(num_runs):
        loss = 2.0 * np.exp(-x / 10) + np.random.randn(epochs) * 0.15
        all_losses.append(loss)

    all_losses = np.array(all_losses)
    mean_loss = all_losses.mean(axis=0)
    std_loss = all_losses.std(axis=0)

    # Create figure
    fig, ax = plt.subplots(figsize=(LINE * 0.7, LINE * 0.5))

    # Plot mean with error bars
    ax.plot(x, mean_loss, linewidth=2, label="Mean", color="#2E86AB")
    ax.fill_between(
        x,
        mean_loss - std_loss,
        mean_loss + std_loss,
        alpha=0.3,
        color="#2E86AB",
        label="±1 std",
    )

    # Plot individual runs with low opacity
    for i, loss in enumerate(all_losses):
        ax.plot(
            x,
            loss,
            linewidth=0.5,
            alpha=0.3,
            color="gray",
            label="Individual run" if i == 0 else None,
        )

    ax.set_xlabel("Epoch")
    ax.set_ylabel("Loss")
    ax.set_title(f"Training Loss (n={num_runs} runs)")
    ax.legend(fontsize=6)
    ax.grid(True, alpha=0.3)

    # Save figure
    save_path = f"{output_dir}/advanced_error_bars.pdf"
    save_fig(fig, save_path)
    plt.close(fig)


def demo_latex_table(output_dir, experiments):
    """Demonstrate generating LaTeX tables."""
    print("\n" + "="*60)
    print("DEMO 4: LaTeX Table Generation")
    print("="*60)

    # Generate results table
    results = []
    for name, data in experiments.items():
        loss = data["loss"]
        accuracy = data["accuracy"]
        config = data["config"]

        results.append({
            "Experiment": name,
            "Learning Rate": config["lr"],
            "Epochs": config["epochs"],
            "Final Loss": f"{loss[-1].item():.4f}",
            "Final Acc": f"{accuracy[-1].item():.4f}",
            "Best Acc": f"{accuracy.max().item():.4f}",
        })

    # Generate LaTeX table
    latex = "\\begin{table}[h]\n"
    latex += "\\centering\n"
    latex += "\\caption{Experimental Results}\n"
    latex += "\\label{tab:results}\n"
    latex += "\\begin{tabular}{lccccc}\n"
    latex += "\\hline\n"
    latex += "Experiment & LR & Epochs & Final Loss & Final Acc & Best Acc \\\\\n"
    latex += "\\hline\n"

    for r in results:
        latex += f"{r['Experiment']} & {r['Learning Rate']} & {r['Epochs']} & "
        latex += f"{r['Final Loss']} & {r['Final Acc']} & {r['Best Acc']} \\\\\n"

    latex += "\\hline\n"
    latex += "\\end{tabular}\n"
    latex += "\\end{table}\n"

    # Save table
    save_path = f"{output_dir}/results_table.tex"
    save_tex(latex, save_path)

    # Also print to console
    print("\nGenerated LaTeX table:")
    print(latex)


def demo_with_store_data(output_dir):
    """Demonstrate loading data from Store and plotting."""
    print("\n" + "="*60)
    print("DEMO 5: Plotting from Store Data")
    print("="*60)

    setup_plt()

    # Create a temporary store with data
    store_parent = tempfile.mkdtemp(prefix="roach_plot_store_")
    store = Store()
    store.init(parent=store_parent, store_id="plot_experiment")

    # Generate and save data
    for i in range(50):
        loss = 2.0 * np.exp(-i / 15) + np.random.randn() * 0.1
        accuracy = 1 - np.exp(-i / 12) + np.random.randn() * 0.05
        store.log("loss", loss)
        store.log("accuracy", accuracy)

    print(f"Created store at: {store.store_dir}")

    # Load and plot
    losses = store.load("loss")
    accuracies = store.load("accuracy")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(LINE, LINE * 0.45))

    # Loss plot
    ax1.plot(losses.numpy(), linewidth=1.5, color="#E63946")
    ax1.set_xlabel("Iteration")
    ax1.set_ylabel("Loss")
    ax1.set_title("Training Loss")
    ax1.grid(True, alpha=0.3)

    # Accuracy plot
    ax2.plot(accuracies.numpy(), linewidth=1.5, color="#06A77D")
    ax2.set_xlabel("Iteration")
    ax2.set_ylabel("Accuracy")
    ax2.set_title("Validation Accuracy")
    ax2.grid(True, alpha=0.3)

    # Save figure
    save_path = f"{output_dir}/store_data_plot.pdf"
    save_fig(fig, save_path)
    plt.close(fig)


def demo_subplot_layouts(output_dir):
    """Demonstrate various subplot layouts."""
    print("\n" + "="*60)
    print("DEMO 6: Subplot Layouts")
    print("="*60)

    setup_plt()

    # Generate sample data
    x = np.linspace(0, 10, 100)
    y1 = np.sin(x)
    y2 = np.cos(x)
    y3 = np.sin(x) * np.exp(-x / 10)
    y4 = np.cos(x) * np.exp(-x / 10)

    # 2x2 grid layout
    fig, axes = plt.subplots(2, 2, figsize=(LINE, LINE * 0.8))

    axes[0, 0].plot(x, y1, linewidth=1.5, color="#264653")
    axes[0, 0].set_title("sin(x)", fontsize=8)
    axes[0, 0].grid(True, alpha=0.3)

    axes[0, 1].plot(x, y2, linewidth=1.5, color="#2A9D8F")
    axes[0, 1].set_title("cos(x)", fontsize=8)
    axes[0, 1].grid(True, alpha=0.3)

    axes[1, 0].plot(x, y3, linewidth=1.5, color="#E76F51")
    axes[1, 0].set_title("sin(x) * exp(-x/10)", fontsize=8)
    axes[1, 0].grid(True, alpha=0.3)

    axes[1, 1].plot(x, y4, linewidth=1.5, color="#F4A261")
    axes[1, 1].set_title("cos(x) * exp(-x/10)", fontsize=8)
    axes[1, 1].grid(True, alpha=0.3)

    # Save figure
    save_path = f"{output_dir}/subplot_layouts.pdf"
    save_fig(fig, save_path)
    plt.close(fig)


def main():
    """Main function running all demonstrations."""
    print("="*60)
    print("ROACH PLOTTING COMPREHENSIVE DEMONSTRATION")
    print("="*60)

    # Create output directory
    output_dir = tempfile.mkdtemp(prefix="roach_plots_")
    print(f"\nOutput directory: {output_dir}")
    print(f"Figure width constant (LINE): {LINE} inches")

    # Generate sample data
    experiments = generate_sample_data()
    print(f"\nGenerated data for {len(experiments)} experiments")

    # Run all demonstrations
    demo_basic_plot(output_dir)
    demo_multi_experiment_plot(output_dir, experiments)
    demo_advanced_plot(output_dir)
    demo_latex_table(output_dir, experiments)
    demo_with_store_data(output_dir)
    demo_subplot_layouts(output_dir)

    # List all generated files
    print("\n" + "="*60)
    print("GENERATED FILES")
    print("="*60)

    output_path = Path(output_dir)
    pdf_files = sorted(output_path.glob("*.pdf"))
    tex_files = sorted(output_path.glob("*.tex"))

    print("\nPDF figures:")
    for f in pdf_files:
        print(f"  - {f.name}")

    print("\nLaTeX tables:")
    for f in tex_files:
        print(f"  - {f.name}")

    print("\n" + "="*60)
    print("DEMONSTRATION COMPLETE")
    print("="*60)
    print(f"\nAll files saved in: {output_dir}")
    print("You can view the PDF files with your preferred PDF viewer.")


if __name__ == "__main__":
    main()
