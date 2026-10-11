import pytest
from app.erp.models import Inventory


def test_inventory_available_calculation():
    """Invariant: available = quantity_on_hand - quantity_reserved"""
    inv = Inventory(quantity_on_hand=100, quantity_reserved=30)
    assert inv.available_quantity == 70
