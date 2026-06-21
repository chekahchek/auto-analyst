import json

def get_assert(output, context):
    expected_value = context["vars"]["expected_value"]
    data_type = json.loads(output).get("data_type", [])
    eval_result = any(expected_value in d for d in data_type)
    return {'pass' : eval_result,
            'score': 1.0 if eval_result else 0.0,
            'reason': f"Returned '{data_type}' instead of '{expected_value}'" if not eval_result else 'Expected value found'}