from collections.abc import Iterator
from typing import Dict, Iterator, List, TypeVar, Union

import pytest
from torch import fx, nn

from ..modules.solver_layers.input_layer import InputLayer
from ..modules.solver_layers.intermediate_layer import IntermediateLayer
from ..modules.solver_layers.output_layer import OutputLayer
from ..preprocessing.graph_module_wrapper import GraphModuleWrapper
from . import preprocessing_utils
from .solver_inputs import SolverInputs
from .transpose import transpose_layer


def build_solver_graph_module(inputs: SolverInputs) -> fx.GraphModule:
    preprocessing_utils.freeze_model(inputs.model)

    graph_wrapper = GraphModuleWrapper(inputs.model, inputs.input_shape)
    unstable_masks = [(L < 0) & (U > 0) for L, U in zip(inputs.L_list, inputs.U_list)]

    # Initially set to solve for input layer.
    C_list, solve_coords = preprocessing_utils.get_C_for_layer(0, unstable_masks)

    L_gen = get_reversed_iterator(inputs.L_list)
    U_gen = get_reversed_iterator(inputs.U_list)
    P_gen = get_reversed_iterator(inputs.P_list)
    P_hat_gen = get_reversed_iterator(inputs.P_hat_list)
    p_gen = get_reversed_iterator(inputs.p_list)
    C_gen = get_reversed_iterator(C_list)

    last_node = graph_wrapper.last_child
    solver_modules: Dict[str, nn.Module] = {}
    graph = fx.Graph()

    transposed_layer, bias_module = transpose_layer(
        last_node.module,
        last_node.input_shape,
        last_node.output_shape,
    )
    output_layer = OutputLayer(
        L=next(L_gen),
        U=next(U_gen),
        C=next(C_gen),
        transposed_layer=transposed_layer,
        bias_module=bias_module,
        H=inputs.H,
        d=inputs.d,
    )
    solver_modules["output_layer"] = output_layer
    prev_output = graph.call_module("output_layer")

    pick_0 = lambda x: x[0]
    pick_1 = lambda x: x[1]
    node = last_node
    while True:
        node = node.parent
        if node is None:
            break
        if not isinstance(node.module, (nn.Linear, nn.Conv2d)):
            continue

        transposed_layer, bias_module = transpose_layer(
            node.module,
            node.input_shape,
            node.output_shape,
        )
        layer = IntermediateLayer(
            L=next(L_gen),
            U=next(U_gen),
            C=next(C_gen),
            transposed_layer=transposed_layer,
            bias_module=bias_module,
            P=next(P_gen),
            P_hat=next(P_hat_gen),
            p=next(p_gen),
        )

        # Decompose the 2 outputs from previous layer, and feed it to the current layer.
        arg_1 = graph.call_function(pick_0, (prev_output,))
        arg_2 = graph.call_function(pick_1, (prev_output,))
        prev_output = graph.call_module(node.name, (arg_1, arg_2))
        solver_modules[node.name] = layer

    solver_modules["input_layer"] = InputLayer(
        L=next(L_gen),
        U=next(U_gen),
        C=next(C_gen),
    )

    arg_1 = graph.call_function(pick_0, (prev_output,))
    arg_2 = graph.call_function(pick_1, (prev_output,))
    prev_output = graph.call_module("input_layer", (arg_1, arg_2))
    graph.output(prev_output)

    # Assert that all generators are depleted.
    for gen in [L_gen, U_gen, P_gen, P_hat_gen, p_gen, C_gen]:  # fmt: skip
        with pytest.raises(StopIteration):
            next(gen)

    return fx.GraphModule(solver_modules, graph)


T = TypeVar("T")


def get_reversed_iterator(list_or_iterator: Union[List[T], Iterator[T]]) -> Iterator[T]:
    items = list(list_or_iterator)
    items.reverse()
    return iter(items)
