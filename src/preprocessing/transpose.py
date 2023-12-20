from typing import Tuple

import torch
from torch import nn

from .class_definitions import (
    Bias,
    Conv2dFlattenBias,
    ConvTranspose2dFlattenNoBias,
    LinearBias,
    UnaryForward,
)


def transpose_layer(
    layer: nn.Module,
    input_shape: Tuple[int, ...],
    output_shape: Tuple[int, ...],
) -> Tuple[UnaryForward, Bias]:
    """Convert `layer` to a transposed of itself without bias, and return it
    along with a `Bias` module that performs the `V_i^T.b` operation, and the
    output features of the tranposed layer.

    Args:
        layer (nn.Module): Layer to transpose.
        input_shape (int): Input shape of `layer`.
        output_shape (int): Output shape of `layer`.

    Returns:
        The tranposed layer, and the corresponding `Bias` module.
    """
    if isinstance(layer, nn.Linear):
        return transpose_linear(layer)
    if isinstance(layer, nn.Conv2d):
        return transpose_conv2d(layer, output_shape)
    if isinstance(layer, nn.Flatten):
        return transpose_flatten(layer, input_shape)
    raise NotImplementedError()


def transpose_linear(linear: nn.Linear) -> Tuple[nn.Linear, Bias]:
    weight = linear.weight
    bias = linear.bias if linear.bias is not None else torch.zeros((weight.size(0),))

    # Create a new Linear layer with transposed weight and without bias
    transposed_linear = nn.Linear(
        in_features=linear.out_features,
        out_features=linear.in_features,
        bias=False,
    )
    transposed_linear.weight = nn.Parameter(weight.t().clone().detach(), requires_grad=False)

    return transposed_linear, LinearBias(bias.clone().detach())


def transpose_conv2d(
    conv2d: nn.Conv2d,
    output_shape: Tuple[int, ...],
) -> Tuple[UnaryForward, Bias]:
    bias = (
        conv2d.bias.clone().detach()
        if conv2d.bias is not None
        else torch.zeros((conv2d.out_channels,))
    )

    return (
        ConvTranspose2dFlattenNoBias(conv2d, output_shape[-3:]),  # type: ignore
        Conv2dFlattenBias(bias),
    )


def transpose_flatten(
    flatten: nn.Flatten,
    input_shape: Tuple[int, ...],
) -> Tuple[nn.Unflatten, Bias]:
    start_dim = (
        flatten.start_dim if flatten.start_dim >= 0 else len(input_shape) + flatten.start_dim
    )
    end_dim = flatten.end_dim if flatten.end_dim >= 0 else len(input_shape) + flatten.end_dim
    unflattened_size = input_shape[start_dim : end_dim + 1]
    return nn.Unflatten(start_dim, unflattened_size), nn.Identity()  # type: ignore


def compute_conv2d_input_shape(
    conv2d: nn.Conv2d,
    output_shape: Tuple[int, int, int],
) -> Tuple[int, int, int]:
    """Calculate the input shape of a Conv2d layer given its configuration and output shape.

    Args:
        conv2d (nn.Conv2d): The 2D CNN layer.
        output_shape (Tuple[int, int, int]): Shape of the output tensor in the form: \
            `(num_channels, height, width)`.

    Returns:
        Tuple[int, int, int]: Input tensor shape in the form: \
            `(num_channels, height, width)`.
    """
    _, out_height, out_width = output_shape
    in_channels = conv2d.in_channels
    kernel_size = conv2d.kernel_size
    stride = conv2d.stride
    padding = conv2d.padding
    assert isinstance(padding, Tuple)

    # Calculating the input height and width
    input_height = (out_height - 1) * stride[0] - 2 * padding[0] + kernel_size[0]
    input_width = (out_width - 1) * stride[1] - 2 * padding[1] + kernel_size[1]

    return (in_channels, input_height, input_width)
