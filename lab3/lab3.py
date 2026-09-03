import json
import math
from datetime import date

def calculator(expression):
    allowed = {
        "sqrt": math.sqrt,
        "pow": pow,
        "pi": math.pi
    }

    return eval(expression, {"__builtins__": {}}, allowed)


def days_between(d1, d2):
    date1 = date.fromisoformat(d1)
    date2 = date.fromisoformat(d2)

    return abs((date2 - date1).days)


def unit_convert(value, frm, to):

    conversions = {
        ("km", "miles"): lambda x: x * 0.621371,
        ("miles", "km"): lambda x: x / 0.621371,

        ("kg", "lb"): lambda x: x * 2.20462,
        ("lb", "kg"): lambda x: x / 2.20462,

        ("C", "F"): lambda x: (x * 9 / 5) + 32,
        ("F", "C"): lambda x: (x - 32) * 5 / 9
    }

    return conversions[(frm, to)](value)

# Maps the tool name to the actual Python function
tools = {
    "calculator": calculator,
    "days_between": days_between,
    "unit_convert": unit_convert
}

schemas = [
    {
        "name": "calculator",
        "description": "Evaluate an arithmetic expression",
        "arguments": {
            "expression": "string"
        }
    },
    {
        "name": "days_between",
        "description": "Find the number of days between two dates",
        "arguments": {
            "d1": "string",
            "d2": "string"
        }
    },
    {
        "name": "unit_convert",
        "description": "Convert between supported units",
        "arguments": {
            "value": "number",
            "frm": "string",
            "to": "string"
        }
    }
]

def dispatch(tool_call):

    # Convert JSON string into Python dictionary
    call = json.loads(tool_call)

    # Get tool name
    name = call["name"]

    # Get arguments
    arguments = call["arguments"]

    # Find the function in our registry
    function = tools[name]

    # Execute the function
    result = function(**arguments)

    # Return observation
    return {
        "tool": name,
        "observation": result
    }


print("TOOLS SHOWN TO MODEL:")
print(json.dumps(schemas, indent=2))

print("\nTOOL CALLS:\n")

calls = [
    '{"name": "calculator", "arguments": {"expression": "sqrt(25) + 2"}}',

    '{"name": "days_between", "arguments": {"d1": "2026-09-01", "d2": "2026-09-10"}}',

    '{"name": "unit_convert", "arguments": {"value": 10, "frm": "km", "to": "miles"}}'
]


for call in calls:

    print("CALL:", call)

    observation = dispatch(call)

    print("OBSERVATION:", observation)
    print()