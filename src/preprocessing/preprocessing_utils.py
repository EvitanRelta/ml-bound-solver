from typing import List, Tuple

import torch
from torch import Tensor, nn
from typing_extensions import TypeAlias


def freeze_model(model: nn.Module) -> None:
    for param in model.parameters():
        param.requires_grad = False


def get_masks(L: List[Tensor], U: List[Tensor]) -> Tuple[List[Tensor], List[Tensor], List[Tensor]]:
    """Returns masks for stably-activated, stably-deactivated and
    unstable neurons in that order.
    """
    num_layers = len(U)
    stably_act_masks: List[Tensor] = [L_i >= 0 for L_i in L]
    stably_deact_masks: List[Tensor] = [U_i <= 0 for U_i in U]
    unstable_masks: List[Tensor] = [(L[i] < 0) & (U[i] > 0) for i in range(num_layers)]
    for i in range(num_layers):
        assert torch.all((stably_act_masks[i] + stably_deact_masks[i] + unstable_masks[i]) == 1)

    return stably_act_masks, stably_deact_masks, unstable_masks


def decompose_model(model: nn.Module) -> Tuple[List[Tensor], List[Tensor]]:
    """Returns the number of linear-layers, linear-layer weights and biases in
    that order.
    """
    linear_layers = [layer for layer in model.children() if isinstance(layer, nn.Linear)]

    W: List[Tensor] = [layer.weight.clone().detach() for layer in linear_layers]
    b: List[Tensor] = [layer.bias.clone().detach() for layer in linear_layers]
    return W, b


NeuronCoords: TypeAlias = Tuple[int, int]
"""Coordinates for a neuron in the model, in the form `(layer_index, neuron_index)`."""


def get_C_for_layer(
    layer_index: int, unstable_masks: List[Tensor]
) -> Tuple[List[Tensor], List[NeuronCoords]]:
    """Get the `C` to solve for the unstable neurons in layer `layer_index`,
    where `layer_index` can be any layer except the last (as we don't solve for
    output layer).

    If `layer_index == 0`, `C` will solve all inputs neurons (irregardless of
    whether they're unstable).
    """
    device = unstable_masks[0].device
    num_layers = len(unstable_masks)
    assert layer_index < num_layers - 1

    C: List[Tensor] = []
    coords: List[NeuronCoords] = []

    # For input layer, solve for all input neurons.
    if layer_index == 0:
        num_input_neurons = len(unstable_masks[0])
        C_0 = torch.zeros((num_input_neurons * 2, num_input_neurons)).to(device)
        batch_index: int = 0
        for index in range(num_input_neurons):
            C_0[batch_index][index] = 1  # Minimising
            C_0[batch_index + 1][index] = -1  # Maximising
            batch_index += 2
            coords.append((0, index))

        C.append(C_0)
        for i in range(1, num_layers):
            mask: Tensor = unstable_masks[i]
            num_neurons: int = len(mask)
            C.append(torch.zeros((num_input_neurons * 2, num_neurons)).to(device))
        return C, coords

    # Else, solve for only unstable neurons in the specified layer.
    num_unstable_in_target_layer = int(unstable_masks[layer_index].sum().item())
    for i in range(num_layers):
        mask: Tensor = unstable_masks[i]
        num_neurons: int = len(mask)
        if i != layer_index:
            C.append(torch.zeros((num_unstable_in_target_layer * 2, num_neurons)).to(device))
            continue

        unstable_indices: Tensor = torch.where(mask)[0]
        C_i = torch.zeros((num_unstable_in_target_layer * 2, num_neurons)).to(device)
        batch_index: int = 0
        for index in unstable_indices:
            C_i[batch_index][index] = 1  # Minimising
            C_i[batch_index + 1][index] = -1  # Maximising
            batch_index += 2
            coords.append((i, int(index.item())))
        C.append(C_i)
    return C, coords
