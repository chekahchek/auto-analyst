class ProfilerError(Exception):
    """Raised when the profiler cannot produce a valid profile."""


class SkillNotFoundError(Exception):
    """Raised when a skill's SKILL.md is missing or resolves outside the skills directory."""
