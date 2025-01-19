from torch import nn
from typing_extensions import override


class Add_SL(nn.Identity):
    """The solver layer for "Add" layers."""

    @override
    def __init__(self) -> None:
        super().__init__()
