"""
Tests for the budget-based restocking recommendation endpoint.
"""
import pytest

from main import build_restocking_recommendation

URL = "/api/restocking/recommendations"
HUGE_BUDGET = 1_000_000_000


def make_item(sku, on_hand, reorder_point, unit_cost, warehouse="Tokyo", category="Sensors"):
    """Build a minimal inventory item for logic-level tests."""
    return {
        "id": sku,
        "sku": sku,
        "name": f"Item {sku}",
        "category": category,
        "warehouse": warehouse,
        "quantity_on_hand": on_hand,
        "reorder_point": reorder_point,
        "unit_cost": unit_cost,
        "location": "Warehouse A-1",
        "last_updated": "2025-09-30T10:30:00",
    }


class TestRestockingEndpoint:
    """Test suite for GET /api/restocking/recommendations."""

    def test_response_structure(self, client):
        """Test the top-level and per-line structure."""
        response = client.get(URL, params={"budget": 2000})
        assert response.status_code == 200

        data = response.json()
        for key in ("budget", "total_cost", "remaining_budget",
                    "full_count", "partial_count", "unfunded_count", "items"):
            assert key in data
        assert data["budget"] == 2000
        assert len(data["items"]) > 0

        line = data["items"][0]
        for key in ("sku", "name", "category", "warehouse", "quantity_on_hand",
                    "reorder_point", "unit_cost", "needed_qty", "recommended_qty",
                    "line_cost", "priority_score", "status", "demand_trend"):
            assert key in line
        assert line["status"] in ("full", "partial", "unfunded")

    def test_zero_budget_funds_nothing(self, client):
        """Test that a zero budget recommends nothing."""
        data = client.get(URL, params={"budget": 0}).json()

        assert data["total_cost"] == 0
        assert data["remaining_budget"] == 0
        assert data["full_count"] == 0
        assert data["partial_count"] == 0
        assert data["unfunded_count"] == len(data["items"])
        assert all(line["recommended_qty"] == 0 for line in data["items"])

    def test_huge_budget_funds_everything_fully(self, client):
        """Test that a very large budget fully funds every candidate."""
        data = client.get(URL, params={"budget": HUGE_BUDGET}).json()

        assert len(data["items"]) > 0
        assert data["unfunded_count"] == 0
        assert data["partial_count"] == 0
        assert data["full_count"] == len(data["items"])
        for line in data["items"]:
            assert line["recommended_qty"] == line["needed_qty"]

    @pytest.mark.parametrize("budget", [0, 100, 500, 2000, 9000, 25000, 100000])
    def test_never_exceeds_budget(self, client, budget):
        """Test that total cost stays within budget and totals add up."""
        data = client.get(URL, params={"budget": budget}).json()

        assert data["total_cost"] <= budget
        assert data["remaining_budget"] == pytest.approx(budget - data["total_cost"])
        assert data["total_cost"] == pytest.approx(
            sum(line["line_cost"] for line in data["items"])
        )
        for line in data["items"]:
            assert line["line_cost"] == pytest.approx(line["recommended_qty"] * line["unit_cost"])
            assert 0 <= line["recommended_qty"] <= line["needed_qty"]

    def test_items_sorted_by_priority(self, client):
        """Test that lines are returned from highest to lowest priority."""
        data = client.get(URL, params={"budget": 2000}).json()

        scores = [line["priority_score"] for line in data["items"]]
        assert scores == sorted(scores, reverse=True)

    def test_status_counts_match_items(self, client):
        """Test that the status counters match the lines."""
        data = client.get(URL, params={"budget": 5000}).json()

        for status in ("full", "partial", "unfunded"):
            expected = len([line for line in data["items"] if line["status"] == status])
            assert data[f"{status}_count"] == expected

    def test_candidates_are_close_to_reorder_point(self, client):
        """Test that only items up to 1.5x reorder point are candidates."""
        data = client.get(URL, params={"budget": HUGE_BUDGET}).json()

        for line in data["items"]:
            assert line["quantity_on_hand"] <= line["reorder_point"] * 1.5

    def test_filter_by_warehouse(self, client):
        """Test filtering recommendations by warehouse."""
        data = client.get(URL, params={"budget": HUGE_BUDGET, "warehouse": "Tokyo"}).json()

        assert len(data["items"]) > 0
        for line in data["items"]:
            assert line["warehouse"] == "Tokyo"

    def test_filter_by_category(self, client):
        """Test filtering recommendations by category."""
        data = client.get(URL, params={"budget": HUGE_BUDGET, "category": "power supplies"}).json()

        assert len(data["items"]) > 0
        for line in data["items"]:
            assert line["category"].lower() == "power supplies"

    def test_all_filter_values_are_ignored(self, client):
        """Test that 'all' behaves like no filter."""
        unfiltered = client.get(URL, params={"budget": 5000}).json()
        with_all = client.get(URL, params={"budget": 5000, "warehouse": "all", "category": "all"}).json()

        assert with_all == unfiltered

    def test_unknown_warehouse_returns_empty(self, client):
        """Test that a filter without matches yields an empty recommendation."""
        data = client.get(URL, params={"budget": 1000, "warehouse": "Atlantis"}).json()

        assert data["items"] == []
        assert data["total_cost"] == 0
        assert data["remaining_budget"] == 1000

    @pytest.mark.parametrize("params", [
        {},                      # budget missing
        {"budget": -1},          # negative
        {"budget": "abc"},       # not a number
        {"budget": "inf"},       # not finite
    ])
    def test_invalid_budget_returns_422(self, client, params):
        """Test that invalid budgets are rejected."""
        response = client.get(URL, params=params)
        assert response.status_code == 422


class TestRestockingLogic:
    """Logic-level tests with controlled inventory (no HTTP)."""

    def test_skips_unaffordable_item_and_funds_cheaper_one(self):
        """Test that an item that does not fit is skipped, not blocking cheaper ones."""
        items = [
            make_item("EXP-1", on_hand=10, reorder_point=50, unit_cost=1000),   # most urgent, expensive
            make_item("CHP-1", on_hand=45, reorder_point=50, unit_cost=2),      # less urgent, cheap
        ]
        result = build_restocking_recommendation(items, [], budget=500)

        by_sku = {line["sku"]: line for line in result["items"]}
        assert [line["sku"] for line in result["items"]] == ["EXP-1", "CHP-1"]
        assert by_sku["EXP-1"]["status"] == "unfunded"
        assert by_sku["EXP-1"]["recommended_qty"] == 0
        assert by_sku["CHP-1"]["status"] == "full"
        assert by_sku["CHP-1"]["recommended_qty"] == 55

    def test_partial_funding_uses_whole_units_only(self):
        """Test that partial funding rounds down to whole units."""
        items = [make_item("PRT-1", on_hand=20, reorder_point=50, unit_cost=30)]  # needs 80 units
        result = build_restocking_recommendation(items, [], budget=100)

        line = result["items"][0]
        assert line["status"] == "partial"
        assert line["recommended_qty"] == 3
        assert line["line_cost"] == 90
        assert result["remaining_budget"] == 10

    def test_target_level_is_twice_reorder_point(self):
        """Test the needed quantity calculation."""
        items = [make_item("TGT-1", on_hand=30, reorder_point=50, unit_cost=1)]
        result = build_restocking_recommendation(items, [], budget=1000)

        assert result["items"][0]["needed_qty"] == 70  # 2 * 50 - 30

    def test_well_stocked_items_are_not_candidates(self):
        """Test that items above 1.5x reorder point are left out."""
        items = [
            make_item("OK-1", on_hand=76, reorder_point=50, unit_cost=1),   # above 75
            make_item("LOW-1", on_hand=75, reorder_point=50, unit_cost=1),  # exactly 1.5x
        ]
        result = build_restocking_recommendation(items, [], budget=1000)

        assert [line["sku"] for line in result["items"]] == ["LOW-1"]

    def test_rising_demand_raises_priority(self):
        """Test that a growing forecast ranks an item above an equally urgent one."""
        items = [
            make_item("AAA-1", on_hand=40, reorder_point=50, unit_cost=1),
            make_item("ZZZ-1", on_hand=40, reorder_point=50, unit_cost=1),
        ]
        forecasts = [{
            "id": "1", "item_sku": "ZZZ-1", "item_name": "Item ZZZ-1",
            "current_demand": 100, "forecasted_demand": 150,
            "trend": "increasing", "period": "Next 30 days",
        }]
        result = build_restocking_recommendation(items, forecasts, budget=1000)

        assert [line["sku"] for line in result["items"]] == ["ZZZ-1", "AAA-1"]
        assert result["items"][0]["demand_trend"] == "increasing"
        assert result["items"][1]["demand_trend"] is None

    def test_falling_demand_does_not_lower_priority(self):
        """Test that the demand factor never drops below 1.0."""
        items = [make_item("FAL-1", on_hand=40, reorder_point=50, unit_cost=1)]
        forecasts = [{
            "id": "1", "item_sku": "FAL-1", "item_name": "Item FAL-1",
            "current_demand": 100, "forecasted_demand": 40,
            "trend": "decreasing", "period": "Next 30 days",
        }]
        with_forecast = build_restocking_recommendation(items, forecasts, budget=1000)
        without_forecast = build_restocking_recommendation(items, [], budget=1000)

        assert with_forecast["items"][0]["priority_score"] == without_forecast["items"][0]["priority_score"]

    def test_ties_are_broken_by_sku(self):
        """Test deterministic ordering for equal scores."""
        items = [
            make_item("B-1", on_hand=40, reorder_point=50, unit_cost=1),
            make_item("A-1", on_hand=40, reorder_point=50, unit_cost=1),
        ]
        result = build_restocking_recommendation(items, [], budget=1000)

        assert [line["sku"] for line in result["items"]] == ["A-1", "B-1"]

    def test_empty_inventory(self):
        """Test that no items gives an empty recommendation with the full budget left."""
        result = build_restocking_recommendation([], [], budget=250)

        assert result["items"] == []
        assert result["total_cost"] == 0
        assert result["remaining_budget"] == 250
