"""
Shared configuration — alert thresholds used across modules, dashboard tabs,
app.py, and tests. Centralized so a threshold is defined once and every
consumer stays in sync (previously duplicated in five separate files).
"""

# Cardiac risk score (0-1) at/above which the cardiac alert fires.
CARDIAC_ALERT_THRESHOLD = 0.6

# Metabolic per-domain score (kidney/liver/glucose, 0-1) at/above which
# that domain's alert fires.
DOMAIN_ALERT_THRESHOLD = 0.5

# Dermatology malignancy score (0-1) at/above which the dermatology alert
# fires.
DERM_ALERT_THRESHOLD = 0.5
