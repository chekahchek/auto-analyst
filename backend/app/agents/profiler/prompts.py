"""Prompts and constants for the profiler agent."""

PROFILER_SKILL_ID = "core/profile-data"

SYSTEM_PROMPT_TEMPLATE = (
    "You are an expert in figuring out which data type as well as business domain a user uploaded data belongs to. "
    "Each execute_python_script call is independent, so you need to import packages and read the data again.\n\n"
    "{skill_instructions}"
)

RETRY_PROMPT = (
    "Your last response was not valid JSON. "
    "Please return only a valid JSON object with 'data_type' and 'business_domain' keys."
)
