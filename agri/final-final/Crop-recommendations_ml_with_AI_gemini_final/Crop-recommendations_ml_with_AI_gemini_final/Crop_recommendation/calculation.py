def calculate_profit(
    land_size,
    yield_per_m2,
    market_price,
    total_fertilizer_cost,
    total_electricity_cost,
    total_labour_cost,
    total_misc_cost
):
    """
    Calculates total yield and net profit.
    ASSUMPTION: Costs provided are TOTAL costs, not per m2.
    """

    # ---- Convert to float ----
    land_size = float(land_size)
    yield_per_m2 = float(yield_per_m2)
    market_price = float(market_price)

    # ---- 1. Calculate Production (Yield) ----
    total_yield = land_size * yield_per_m2

    # ---- 2. Calculate Revenue ----
    revenue = total_yield * market_price

    # ---- 3. Calculate Total Expenses ----
    # We simply sum up the inputs (assuming user entered total bills)
    total_cost = (
        float(total_fertilizer_cost) + 
        float(total_electricity_cost) + 
        float(total_labour_cost) + 
        float(total_misc_cost)
    )

    # ---- 4. Net Profit ----
    net_profit = revenue - total_cost

    return total_yield, revenue, total_cost, net_profit