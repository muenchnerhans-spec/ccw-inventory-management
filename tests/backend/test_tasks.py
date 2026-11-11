"""
Tests for the /api/tasks endpoints and the quarter helper used by the reports.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def clean_tasks():
    """Keep the in-memory task list isolated between tests."""
    main.tasks.clear()
    yield
    main.tasks.clear()


class TestTasks:
    """Test suite for /api/tasks."""

    def test_list_starts_empty(self, client):
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task_returns_201_and_is_listed_first(self, client):
        first = client.post("/api/tasks", json={"title": "First", "priority": "high", "dueDate": "2025-12-01"})
        second = client.post("/api/tasks", json={"title": "Second", "dueDate": "2025-12-02"})

        assert first.status_code == 201
        assert first.json()["status"] == "pending"
        assert first.json()["priority"] == "high"
        assert second.json()["priority"] == "medium"
        assert first.json()["id"] != second.json()["id"]

        titles = [t["title"] for t in client.get("/api/tasks").json()]
        assert titles == ["Second", "First"]

    def test_create_task_requires_title_and_due_date(self, client):
        assert client.post("/api/tasks", json={"dueDate": "2025-12-01"}).status_code == 422
        assert client.post("/api/tasks", json={"title": "No date"}).status_code == 422

    def test_ids_are_not_reused_after_delete(self, client):
        a = client.post("/api/tasks", json={"title": "A", "dueDate": "2025-12-01"}).json()
        b = client.post("/api/tasks", json={"title": "B", "dueDate": "2025-12-01"}).json()
        client.delete(f"/api/tasks/{b['id']}")
        c = client.post("/api/tasks", json={"title": "C", "dueDate": "2025-12-01"}).json()

        # The surviving task keeps its id and the new one doesn't collide with it
        assert c["id"] != a["id"]
        assert len({t["id"] for t in client.get("/api/tasks").json()}) == 2

    def test_toggle_flips_status_back_and_forth(self, client):
        task = client.post("/api/tasks", json={"title": "T", "dueDate": "2025-12-01"}).json()

        done = client.patch(f"/api/tasks/{task['id']}")
        assert done.status_code == 200
        assert done.json()["status"] == "completed"

        reopened = client.patch(f"/api/tasks/{task['id']}")
        assert reopened.json()["status"] == "pending"

    def test_delete_removes_task(self, client):
        task = client.post("/api/tasks", json={"title": "T", "dueDate": "2025-12-01"}).json()

        assert client.delete(f"/api/tasks/{task['id']}").status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_unknown_task_returns_404(self, client):
        assert client.patch("/api/tasks/nope").status_code == 404
        assert client.delete("/api/tasks/nope").status_code == 404


class TestQuarterLabel:
    """Quarters are derived from the date, not hardcoded to 2025."""

    @pytest.mark.parametrize("date,expected", [
        ("2025-01-15", "Q1-2025"),
        ("2025-03-31", "Q1-2025"),
        ("2025-04-01", "Q2-2025"),
        ("2025-12-31", "Q4-2025"),
        ("2026-02-10", "Q1-2026"),
        ("2024-07-04", "Q3-2024"),
    ])
    def test_valid_dates(self, date, expected):
        assert main.quarter_label(date) == expected

    @pytest.mark.parametrize("date", ["", "garbage", "2025-13-01", "2025-00-10", None])
    def test_invalid_dates_return_none(self, date):
        assert main.quarter_label(date) is None
