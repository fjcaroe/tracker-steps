"""Compare private cold restores only within the matching Community product cohort."""
import re


def converted_profile(source, target):
    endings = r"[A-Z0-9_]{1,25}"
    profiles = (
        ("COMMUNITY_SYS_PREVIRED_COHORT_", "COMMUNITY_SYS_PREVIRED_RECOVERY_", "sys"),
        ("COMMUNITY_PAYROLL_CERRO_REVIEW_", "COMMUNITY_CERRO_PAYROLL_RECOVERY_", "cerro"),
    )
    for original, restored, name in profiles:
        if re.fullmatch(original + endings, source) and re.fullmatch(restored + endings, target):
            return name
    raise ValueError("A private source and recovery copy of the same converted product are required")
