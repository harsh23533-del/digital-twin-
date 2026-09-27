"""
Shared configuration — alert thresholds used across modules, dashboard tabs,
app.py, and tests. Centralized so a threshold is defined once and every
consumer stays in sync.
"""

# Cardiac risk score (0-1) at/above which the cardiac alert fires.
CARDIAC_ALERT_THRESHOLD = 0.6
