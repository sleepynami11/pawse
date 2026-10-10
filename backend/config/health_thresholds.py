# -*- coding: utf-8 -*-
"""
Health Anomaly Thresholds Configuration (V3.3.9)
================================================

Configurable health thresholds for cat health monitoring.
These can be adjusted based on breed, age, or individual cat profiles.
"""

HEALTH_ANOMALY_THRESHOLDS = {
    'temperature': {
        'normal_min': 37.5,
        'normal_max': 39.2,
        'warning_high': 39.5,
        'critical_high': 40.0,
        'warning_low': 37.0,
        'critical_low': 36.5
    },
    'heart_rate': {
        'normal_min': 120,
        'normal_max': 240,
        'warning_low': 100,
        'critical_low': 80,
        'warning_high': 260,
        'critical_high': 280
    },
    'activity_level': {
        'normal_min': 10,
        'warning_low': 5,
        'critical_low': 2
    }
}


def get_thresholds_for_cat(cat_profile: dict = None) -> dict:
    """
    Get adjusted thresholds based on cat profile (age, breed).

    Args:
        cat_profile: Dictionary containing cat profile information
                     Expected keys: age_years, breed, weight_kg

    Returns:
        Dictionary of adjusted thresholds
    """
    import copy
    thresholds = copy.deepcopy(HEALTH_ANOMALY_THRESHOLDS)

    if cat_profile:
        age = cat_profile.get('age_years', 5)
        breed = cat_profile.get('breed', 'domestic')

        # Adjust for senior cats (10+ years)
        if age >= 10:
            thresholds['activity_level']['normal_min'] = 5
            thresholds['activity_level']['warning_low'] = 3
            thresholds['heart_rate']['normal_min'] = 110

        # Adjust for kitten (<1 year)
        elif age < 1:
            thresholds['heart_rate']['normal_min'] = 140
            thresholds['heart_rate']['normal_max'] = 260
            thresholds['temperature']['normal_max'] = 39.5

        # Breed-specific adjustments
        if breed.lower() in ['persian', 'exotic']:
            # Brachycephalic breeds may have higher resting heart rates
            thresholds['heart_rate']['normal_max'] = 260
        elif breed.lower() in ['maine_coon', 'ragdoll']:
            # Large breeds may have lower heart rates
            thresholds['heart_rate']['normal_min'] = 110

    return thresholds
