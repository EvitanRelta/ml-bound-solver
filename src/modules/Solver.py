from typing import Tuple

import torch
from torch import Tensor, nn

from ..preprocessing.solver_inputs import SolverInputs
from .AdversarialCheckModel import AdversarialCheckModel
from .solver_layers.SolverSequential import SolverSequential


class Solver(nn.Module):
    def __init__(self, inputs: SolverInputs):
        super().__init__()
        self.sequential = SolverSequential(inputs)
        self.adv_check_model = AdversarialCheckModel(inputs.model, inputs.ground_truth_neuron_index)

    def reset_and_solve_for_layer(self, layer_index: int) -> None:
        self.sequential.solve_for_layer(layer_index)

    def clamp_parameters(self):
        self.sequential.clamp_parameters()

    def forward(self) -> Tuple[Tensor, Tensor]:
        max_objective, theta = self.sequential.forward()
        self.last_max_objective = max_objective.detach()
        return max_objective, theta

    def get_updated_bounds(self, layer_index: int) -> Tuple[Tensor, Tensor]:
        """Returns `(new_lower_bounds, new_upper_bounds)` for layer `layer_index`."""
        assert self.sequential.solve_coords[0][0] == layer_index

        # Clone the tensors to avoid modifying the original tensors
        new_L: Tensor = self.sequential[layer_index].L.clone().detach()
        new_U: Tensor = self.sequential[layer_index].U.clone().detach()

        # Iterate over the solve_coords
        for i, (_, coord) in enumerate(self.sequential.solve_coords):
            # Replace bounds only if they're better than the initial bounds.
            new_L[coord] = torch.max(new_L[coord], self.last_max_objective[2 * i])
            # New upper bounds is negation of objective func.
            new_U[coord] = torch.min(new_U[coord], -self.last_max_objective[2 * i + 1])

        return new_L, new_U
