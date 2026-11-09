"""
Tests for the reports endpoints (quarterly performance and monthly trends).
"""


class TestQuarterlyReports:
    """Test suite for GET /api/reports/quarterly."""

    def test_unfiltered_structure(self, client):
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for row in data:
            for field in ("quarter", "total_orders", "total_revenue", "delivered_orders",
                          "avg_order_value", "fulfillment_rate"):
                assert field in row
        assert [r["quarter"] for r in data] == sorted(r["quarter"] for r in data)

    def test_warehouse_filter_reduces_orders(self, client):
        all_orders = sum(r["total_orders"] for r in client.get("/api/reports/quarterly").json())
        filtered = client.get("/api/reports/quarterly", params={"warehouse": "Tokyo"}).json()
        filtered_orders = sum(r["total_orders"] for r in filtered)

        assert 0 < filtered_orders < all_orders
        expected = len([o for o in client.get("/api/orders", params={"warehouse": "Tokyo"}).json()
                        if o["order_date"][:4] == "2025"])
        assert filtered_orders == expected

    def test_status_filter_gives_full_fulfillment(self, client):
        data = client.get("/api/reports/quarterly", params={"status": "Delivered"}).json()
        assert len(data) > 0
        assert all(r["fulfillment_rate"] == 100.0 for r in data)

    def test_month_filter_limits_to_one_quarter(self, client):
        data = client.get("/api/reports/quarterly", params={"month": "2025-02"}).json()
        assert [r["quarter"] for r in data] == ["Q1-2025"]

    def test_all_values_behave_like_no_filter(self, client):
        unfiltered = client.get("/api/reports/quarterly").json()
        with_all = client.get("/api/reports/quarterly", params={
            "warehouse": "all", "category": "all", "status": "all", "month": "all"
        }).json()
        assert with_all == unfiltered


class TestMonthlyTrends:
    """Test suite for GET /api/reports/monthly-trends."""

    def test_unfiltered_structure(self, client):
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for row in data:
            for field in ("month", "order_count", "revenue", "delivered_count"):
                assert field in row
        assert [r["month"] for r in data] == sorted(r["month"] for r in data)

    def test_month_filter_returns_single_month(self, client):
        data = client.get("/api/reports/monthly-trends", params={"month": "2025-03"}).json()
        assert [r["month"] for r in data] == ["2025-03"]

    def test_quarter_filter_returns_three_months(self, client):
        data = client.get("/api/reports/monthly-trends", params={"month": "Q2-2025"}).json()
        assert [r["month"] for r in data] == ["2025-04", "2025-05", "2025-06"]

    def test_category_filter_reduces_revenue(self, client):
        total = sum(r["revenue"] for r in client.get("/api/reports/monthly-trends").json())
        filtered = sum(r["revenue"] for r in client.get(
            "/api/reports/monthly-trends", params={"category": "sensors"}).json())
        assert 0 < filtered < total

    def test_unknown_warehouse_returns_empty_list(self, client):
        response = client.get("/api/reports/monthly-trends", params={"warehouse": "Atlantis"})
        assert response.status_code == 200
        assert response.json() == []
