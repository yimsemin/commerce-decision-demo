from __future__ import annotations


def test_expected_datasets_present(datasets):
    assert set(datasets.keys()) == {"orders", "marketing", "inventory", "customers", "skus"}


def test_orders_schema(datasets):
    df = datasets["orders"]
    expected_cols = {
        "order_id",
        "order_date",
        "brand",
        "channel",
        "sku_id",
        "customer_id",
        "is_new_customer",
        "quantity",
        "selling_price",
        "discount",
        "net_sales",
    }
    assert expected_cols.issubset(df.columns)
    assert not df.isnull().any().any()
    assert df["order_id"].is_unique
    assert (df["quantity"] > 0).all()
    assert (df["net_sales"] >= 0).all()
    assert len(df) > 1000


def test_marketing_schema(datasets):
    df = datasets["marketing"]
    expected_cols = {
        "date",
        "brand",
        "marketing_channel",
        "spend",
        "impressions",
        "clicks",
        "attributed_orders",
        "attributed_revenue",
    }
    assert expected_cols.issubset(df.columns)
    assert not df.isnull().any().any()
    assert (df["spend"] > 0).all()
    assert (df["impressions"] >= df["clicks"]).all()


def test_inventory_schema(datasets):
    df = datasets["inventory"]
    expected_cols = {
        "date",
        "sku_id",
        "brand",
        "opening_stock",
        "receipts",
        "units_sold",
        "closing_stock",
    }
    assert expected_cols.issubset(df.columns)
    assert not df.isnull().any().any()
    assert (df["closing_stock"] >= 0).all()
    assert (df["opening_stock"] >= 0).all()

    # opening/closing stock must be internally consistent day over day
    check = df.copy()
    check["expected_closing"] = check["opening_stock"] + check["receipts"] - check["units_sold"]
    assert (check["closing_stock"] == check["expected_closing"]).all()


def test_customers_schema(datasets):
    df = datasets["customers"]
    expected_cols = {
        "customer_id",
        "acquisition_channel",
        "first_order_date",
        "total_orders",
        "total_net_sales",
        "is_returning",
    }
    assert expected_cols.issubset(df.columns)
    assert not df.isnull().any().any()
    assert df["customer_id"].is_unique
    assert (df["total_orders"] > 0).all()


def test_skus_schema(datasets):
    df = datasets["skus"]
    assert set(df.columns) == {"sku_id", "brand", "base_price", "unit_cost"}
    assert df["sku_id"].is_unique
    assert (df["base_price"] > df["unit_cost"]).all()
