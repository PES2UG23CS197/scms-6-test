"""Comprehensive unit tests for the Supply Chain Management System (SCMS) database layer."""

from decimal import Decimal
import pytest

from db.queries import (
    add_product, get_all_products, update_product, delete_product,
    add_inventory, get_inventory, get_low_stock, delete_inventory_for_sku,
    move_product, get_route_cost, get_cheapest_route_details,
    get_products_by_warehouse, get_inventory_locations_for_sku,
    get_customer_locations, get_locations, get_inventory_for_sku,
    place_order, get_orders, update_order_status, delete_order,
    add_forecast, get_forecast, get_inventory_for_forecast,
    generate_summary_report, reset_simulation as db_reset_simulation,
    get_connection, move_order_to_customer, validate_user,
    suggest_cheapest_origin, create_user, write_log, get_logs,
    get_valid_origins_for_destination, get_all_warehouse_locations,
    get_logistics_records
)


# ---------------------- SETUP ---------------------- #
@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Reset database to base state before running tests."""
    db_reset_simulation()


# ---------------------- F-001: Add/Edit/Delete Product ---------------------- #
def test_add_update_delete_product():
    """Test adding, updating, and deleting a product."""
    sku = "TESTSKU"
    delete_product(sku)
    add_product(sku, "Test Product", "Test Desc", 5)
    products = get_all_products()
    assert any(p[0] == sku for p in products)

    update_product(sku, "Updated Name", "Updated Desc", 10)
    updated = [p for p in get_all_products() if p[0] == sku][0]
    assert updated[1] == "Updated Name"
    assert updated[2] == "Updated Desc"
    assert updated[3] == 10

    delete_product(sku)
    products = get_all_products()
    assert not any(p[0] == sku for p in products)


# ---------------- F-002 & F-003: Inventory Tracking & Low Stock Alert ---------------- #
def test_inventory_tracking_and_alert():
    """Test inventory tracking and low stock alert behavior."""
    sku = "SKU001"
    location = "Warehouse A"
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM Inventory WHERE sku = %s AND location = %s",
        (sku, location),
    )
    conn.commit()

    add_inventory(sku, location, 3)
    inventory = get_inventory()
    assert any(i[1] == sku and i[2] == location for i in inventory)

    low_stock = get_low_stock()
    assert any(i[0] == sku and i[2] == location for i in low_stock)

    cursor.close()
    conn.close()


# ---------------- F-004, F-005, F-008: Move Product & Route Optimization ---------------- #
def test_move_product_and_cost():
    """Test moving a product and verifying transport cost."""
    sku = "SKU001"
    origin = "Warehouse A"
    destination = "Retail Hub 1"
    quantity = 1

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM Inventory WHERE sku = %s AND location IN (%s, %s)",
        (sku, origin, destination),
    )
    cursor.execute(
        "INSERT INTO Inventory (sku, location, quantity) VALUES (%s, %s, %s)",
        (sku, origin, 20),
    )
    conn.commit()

    cost = get_route_cost(origin, destination)
    assert cost is not None

    route = get_cheapest_route_details(origin, destination)
    assert route["cost"] == cost

    move_product(sku, origin, destination, quantity, cost)
    inventory = get_inventory()
    dest_qty = [i[3] for i in inventory if i[1] == sku and i[2] == destination]
    assert dest_qty and dest_qty[0] >= quantity

    cursor.close()
    conn.close()


def test_move_product_insufficient_stock():
    """Test move_product raises ValueError for insufficient stock."""
    sku = "SKU001"
    origin = "Warehouse A"
    destination = "Retail Hub 1"
    with pytest.raises(ValueError):
        move_product(sku, origin, destination, 9999, 10.0)


# ---------------------- F-006: Order Management ---------------------- #
def test_order_flow():
    """Test placing, updating, and deleting customer orders."""
    sku = "SKU001"
    user = "TestUser"
    location = "Retail Hub 1"

    place_order(sku, 2, user, location)
    orders = get_orders(user, "User")
    assert any(o[1] == sku and o[3] == user for o in orders)

    order_id = orders[0][0]
    update_order_status(order_id, "Processed")
    updated = get_orders(user, "User")[0]
    assert updated[5] == "Processed"

    delete_order(order_id)
    orders = get_orders(user, "User")
    assert not any(o[0] == order_id for o in orders)


# ---------------------- F-007: Forecast Demand ---------------------- #
def test_forecast_and_gap():
    """Test adding a forecast and verifying available inventory."""
    sku = "SKU001"
    add_forecast(sku, 10, "2025-11-10")
    forecasts = get_forecast()
    assert any(f[0] == sku for f in forecasts)

    inventory = get_inventory_for_forecast(sku)
    assert isinstance(inventory, (int, float, Decimal))


# ---------------------- F-009: Reporting ---------------------- #
def test_summary_report():
    """Test that the summary report returns all expected fields."""
    report = generate_summary_report()
    assert "Total Orders" in report
    assert "Processed Orders" in report
    assert "Low Stock Items" in report
    assert "Total Logistics Cost" in report


# ---------------------- F-010: Simulation Reset ---------------------- #
@pytest.mark.timeout(10)
def test_reset_simulation():
    """Test that simulation reset successfully restores base data."""
    db_reset_simulation()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Products")
    count = cursor.fetchone()[0]
    assert count >= 3
    cursor.close()
    conn.close()


# ---------------------- EXTRA COVERAGE: Logistics, Auth, and Utils ---------------------- #
def test_move_order_to_customer_and_validation():
    """Test moving an order to a customer and validating user credentials."""
    sku = "SKU001"
    origin = "Warehouse A"
    destination = "Retail Hub 1"
    quantity = 1
    move_order_to_customer(1, sku, quantity, origin, destination)

    # Validate existing admin user
    user = validate_user("admin1", "adminpass123")
    assert user and user["role"] in ("Admin", "User")


def test_create_user_and_suggest_cheapest_origin():
    """Test user creation and cheapest origin suggestion."""
    create_user("pytest_user", "pytest_pass")
    suggestion = suggest_cheapest_origin("SKU001", "Retail Hub 1")
    assert suggestion is None or "origin" in suggestion


def test_logging_functions():
    """Test write_log and get_logs functions."""
    write_log(1, "Test log entry")
    logs = get_logs()
    assert any("Test log entry" in l[1] for l in logs)


def test_warehouse_location_functions():
    """Test warehouse and origin-related utility functions."""
    sku = "SKU001"
    destination = "Retail Hub 1"

    valid_origins = get_valid_origins_for_destination(destination, sku)
    assert isinstance(valid_origins, list)

    warehouses = get_all_warehouse_locations()
    assert isinstance(warehouses, list)
    assert all(isinstance(loc, str) for loc in warehouses)


# ---------------------- ADDITIONAL COVERAGE TESTS ---------------------- #
def test_get_products_by_warehouse_and_delete_inventory_for_sku():
    """Test fetching products by warehouse and deleting inventory for a SKU."""
    sku = "SKU002"

    # Ensure no duplicate exists before insert (fixes CI/ repeated-run failures)
    delete_inventory_for_sku(sku)

    add_inventory(sku, "Warehouse B", 5)
    products = get_products_by_warehouse("Warehouse B")
    assert any(p[0] == sku for p in products)

    # Clean up to avoid leaving duplicates on subsequent runs
    delete_inventory_for_sku(sku)


def test_get_inventory_locations_and_customer_locations():
    """Test functions returning locations and routes."""
    sku = "SKU001"
    inv_locs = get_inventory_locations_for_sku(sku)
    assert isinstance(inv_locs, list)

    cust_locs = get_customer_locations()
    assert any("Retail Hub" in loc for loc in cust_locs)


def test_get_locations_returns_valid_tuples():
    """Test get_locations returns valid origins and destinations."""
    origins, destinations = get_locations()
    assert isinstance(origins, list)
    assert isinstance(destinations, list)
    assert all(isinstance(o, str) for o in origins)
    assert all(isinstance(d, str) for d in destinations)


def test_get_inventory_for_sku_and_logistics_records():
    """Test inventory for SKU and logistics records functions."""
    sku = "SKU001"
    inv = get_inventory_for_sku(sku)
    assert isinstance(inv, list)

    records = get_logistics_records()
    assert isinstance(records, list)


def test_move_order_to_customer_no_route():
    """Test move_order_to_customer raises ValueError when no route exists."""
    with pytest.raises(ValueError):
        move_order_to_customer(99, "SKU001", 1, "Warehouse A", "Nowhere Land")


def test_get_route_cost_and_cheapest_route_no_result():
    """Test get_route_cost and get_cheapest_route_details for invalid route."""
    result = get_route_cost("X", "Y")
    assert result is None

    details = get_cheapest_route_details("X", "Y")
    assert details is None


def test_validate_user_invalid_and_summary_report_values():
    """Test invalid user validation and summary report numeric values."""
    invalid = validate_user("fakeuser", "fakepass")
    assert invalid is None

    report = generate_summary_report()
    assert isinstance(report["Total Orders"], int)
    assert isinstance(report["Low Stock Items"], int)


def test_forecast_and_inventory_zero_case():
    """Test get_inventory_for_forecast when SKU does not exist."""
    val = get_inventory_for_forecast("NONEXISTENTSKU")
    assert val == 0











def test_update_inventory_functionality():
    """Test update_inventory directly to cover its code path."""
    sku = "SKU_UPDATE"
    location = "Warehouse C"

    # Ensure clean state
    delete_inventory_for_sku(sku)
    add_inventory(sku, location, 5)

    # Update quantity
    from db.queries import update_inventory
    update_inventory(sku, location, 15)

    inv = get_inventory()
    updated = [i for i in inv if i[1] == sku and i[2] == location][0]
    assert updated[3] == 15


def test_move_product_insert_branch():
    """Test move_product when destination does not exist (covers INSERT branch)."""
    sku = "SKU_INSERT"
    origin = "Warehouse D"
    destination = "Retail Hub 2"

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Inventory WHERE sku = %s", (sku,))
    conn.commit()

    # Add only origin
    add_inventory(sku, origin, 10)

    cost = get_route_cost(origin, destination)
    move_product(sku, origin, destination, 2, cost)

    inv = get_inventory()
    dest_qty = [i[3] for i in inv if i[1] == sku and i[2] == destination]
    assert dest_qty and dest_qty[0] >= 2

    cursor.close()
    conn.close()


def test_get_orders_admin_branch():
    """Test get_orders with Admin role to cover that branch."""
    sku = "SKU001"
    user = "AdminTest"
    location = "Retail Hub 1"

    # Place an order
    place_order(sku, 1, user, location)

    # Admin should see all orders
    orders = get_orders(role="Admin")
    assert any(o[1] == sku for o in orders)

