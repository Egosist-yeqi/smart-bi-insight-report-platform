"""Small CPU-only PyTorch adapter for the optional trend forecast engine.

The default OLS engine stays dependency-free and reproducible. PyTorch is only
loaded when the deployment explicitly enables it, so normal demonstrations do
not need a large ML runtime or GPU.
"""

from decimal import Decimal, ROUND_HALF_UP


def forecast_linear(values: list[Decimal]) -> tuple[Decimal, Decimal] | None:
    """Return ``(next_value, slope)`` from a least-squares PyTorch fit.

    ``None`` means the optional runtime is unavailable or the history is too
    short. The caller then uses the deterministic OLS fallback.
    """

    if len(values) < 2:
        return None

    try:
        import torch
    except ModuleNotFoundError:
        return None

    x = torch.arange(len(values), dtype=torch.float64)
    y = torch.tensor([float(value) for value in values], dtype=torch.float64)
    design = torch.column_stack((torch.ones_like(x), x))
    coefficients = torch.linalg.lstsq(design, y).solution
    intercept, slope = coefficients.tolist()
    prediction = intercept + slope * len(values)
    return (
        Decimal(str(prediction)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
        Decimal(str(slope)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
    )
