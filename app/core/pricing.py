# app/core/pricing.py

"""
This module encapsulates the pricing logic for the products.
It contains the price list and functions to calculate the cost of an order.
"""

# Price list based on 4dev/info/calculator_from_website_banners.md
# Structure: PRICES[product_type][material_id][dpi] = price_per_square_meter.
PRICES = {
    "banners": {
        "frontlit_440": {
            "540": 749.0,
            "720": 949.0,
            "1440": 1200.0,
        },
        "frontlit_cast_530": {
            "540": 1068.0,
            "720": 1428.0,
            "1440": 1880.0,
        },
        "blackout": {
            "540": 1547.0,
            "720": 2147.0,
            "1440": 2900.0,
        },
        "backlit": {
            "540": 1108.0,
            "720": 1488.0,
            "1440": 1965.0,
        },
        "mesh": {
            "540": 650.0,
            "720": 950.0,
            "1440": 1000.0,
        },
    }
}

URGENCY_SURCHARGE_PERCENT = 50
DELIVERY_COST = 350.0
MINIMUM_AREA = 1.0


def calculate_price(
    product: str,
    material: str | None,
    width: float,
    height: float,
    dpi: str | None,
    is_urgent: bool,
    quantity: int = 1,
    needs_delivery: bool = False,
) -> float | None:
    """
    Calculates the total price for a given product based on a full set of parameters.
    """
    try:
        # Ensure all required parameters are provided
        if not all([product, material, dpi]):
            return None

        price_per_sq_meter = PRICES[product][material][dpi]
        area = max(width * height, MINIMUM_AREA)  # Enforce minimum order area
        total_price = price_per_sq_meter * area * quantity

        if is_urgent:
            total_price *= 1 + (URGENCY_SURCHARGE_PERCENT / 100)

        if needs_delivery:
            total_price += DELIVERY_COST

        return total_price
    except KeyError:
        # Handle cases where the product or material is not in our price list.
        return None