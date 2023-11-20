from typing import List, Optional

import matplotlib.pyplot as plt
import numpy as np
import torch
from torch import Tensor

from .inputs.save_file_types import GurobiResults


def compare_against_gurobi(
    new_L_list: List[Tensor],
    new_U_list: List[Tensor],
    unstable_masks: List[Tensor],
    initial_L_list: List[Tensor],
    initial_U_list: List[Tensor],
    gurobi_results: GurobiResults,
    cutoff_threshold: Optional[float] = None,
) -> None:
    # Ensure all tensors are on same device.
    device = torch.device("cpu")
    new_L_list = [L.to(device) for L in new_L_list]
    new_U_list = [U.to(device) for U in new_U_list]
    unstable_masks = [mask.to(device) for mask in unstable_masks]
    initial_L_list = [L.to(device) for L in initial_L_list]
    initial_U_list = [U.to(device) for U in initial_U_list]
    gurobi_results["L_list_unstable_only"] = [
        L.to(device) for L in gurobi_results["L_list_unstable_only"]
    ]
    gurobi_results["U_list_unstable_only"] = [
        U.to(device) for U in gurobi_results["U_list_unstable_only"]
    ]

    # Only consider input + unstable intermediates neurons.
    masks = unstable_masks[1:-1]
    unstable_L_list = [initial_L_list[0]] + [
        L[mask] for (L, mask) in zip(initial_L_list[1:-1], masks)
    ]
    unstable_U_list = [initial_U_list[0]] + [
        U[mask] for (U, mask) in zip(initial_U_list[1:-1], masks)
    ]
    unstable_new_L_list = [new_L_list[0]] + [L[mask] for (L, mask) in zip(new_L_list[1:-1], masks)]
    unstable_new_U_list = [new_U_list[0]] + [U[mask] for (U, mask) in zip(new_U_list[1:-1], masks)]
    gurobi_L_list = gurobi_results["L_list_unstable_only"][:-1]
    gurobi_U_list = gurobi_results["U_list_unstable_only"][:-1]

    list_len: int = len(unstable_new_L_list)

    # Assert that all bounds lists are of same length/shape.
    assert (
        len(unstable_L_list)
        == len(unstable_U_list)
        == len(unstable_new_L_list)
        == len(unstable_new_U_list)
        == len(gurobi_L_list)
        == len(gurobi_U_list)
    )
    for i in range(list_len):
        assert (
            unstable_L_list[i].shape
            == unstable_U_list[i].shape
            == unstable_new_L_list[i].shape
            == unstable_new_U_list[i].shape
            == gurobi_L_list[i].shape
            == gurobi_U_list[i].shape
        )

    diff_L_list: List[Tensor] = [gurobi_L_list[i] - unstable_L_list[i] for i in range(list_len)]
    diff_U_list: List[Tensor] = [unstable_U_list[i] - gurobi_U_list[i] for i in range(list_len)]
    diff_new_L_list: List[Tensor] = [
        gurobi_L_list[i] - unstable_new_L_list[i] for i in range(list_len)
    ]
    diff_new_U_list: List[Tensor] = [
        unstable_new_U_list[i] - gurobi_U_list[i] for i in range(list_len)
    ]

    if cutoff_threshold:
        non_zero_L_mask: List[Tensor] = [(x > cutoff_threshold) for x in diff_L_list]
        non_zero_U_mask: List[Tensor] = [(x > cutoff_threshold) for x in diff_U_list]

        diff_L_list = [diff_L_list[i][non_zero_L_mask[i]] for i in range(list_len)]
        diff_U_list = [diff_U_list[i][non_zero_U_mask[i]] for i in range(list_len)]
        diff_new_L_list = [diff_new_L_list[i][non_zero_L_mask[i]] for i in range(list_len)]
        diff_new_U_list = [diff_new_U_list[i][non_zero_U_mask[i]] for i in range(list_len)]

    plot_box_and_whiskers(
        [diff_L_list, diff_U_list, diff_new_L_list, diff_new_U_list],
        ["initial lower bounds", "initial upper bounds", "new lower bounds", "new upper bounds"],
        title="Difference between computed bounds vs Gurobi's"
        + f"\n(excluding neurons whr initial-vs-Gurobi diff values <= {cutoff_threshold})",
        xlabel="Differences",
        ylabel="Bounds",
    )


def plot_box_and_whiskers(
    values: List[List[Tensor]],
    labels: List[str],
    title: str,
    xlabel: str,
    ylabel: str,
) -> None:
    concat_values: List[np.ndarray] = [torch.cat(x).numpy() for x in values]

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.boxplot(concat_values, vert=False, labels=labels)

    ax.set_title(title)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)

    plt.tight_layout()
    plt.show()
