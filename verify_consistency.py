#!/usr/bin/env python
"""
Permanent verification script to ensure order counts remain consistent.
Run this anytime to verify dashboard home and orders page counts match.
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append('/Users/teslimadekoya/Desktop/ADMOS TEST/food_ordering')

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'food_ordering.settings')
django.setup()

from dashboard.views import get_active_orders_count, get_pending_orders_count, get_on_the_way_orders_count

def verify_consistency():
    """Verify that order counts are consistent across the system."""
    
    print("🔍 Verifying Order Count Consistency...")
    print("=" * 50)
    
    # Get counts using centralized functions
    active_count = get_active_orders_count()
    pending_count = get_pending_orders_count()
    on_the_way_count = get_on_the_way_orders_count()
    
    print(f"📊 Dashboard Home Count: {active_count}")
    print(f"📋 Orders Page - Pending: {pending_count}")
    print(f"🚚 Orders Page - On the Way: {on_the_way_count}")
    print(f"📋 Orders Page Total: {pending_count + on_the_way_count}")
    
    # Verify consistency
    if active_count == (pending_count + on_the_way_count):
        print("\n✅ SUCCESS: Counts are consistent!")
        print("🎉 Dashboard home and orders page counts match perfectly!")
        return True
    else:
        print("\n❌ ERROR: Counts are inconsistent!")
        print("🚨 This should never happen with centralized functions!")
        return False

if __name__ == "__main__":
    verify_consistency()
