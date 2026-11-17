from fractions import Fraction
import json

RESULT_FORMAT_VERSION = 1

def encode_value(value):
    if isinstance(value, Fraction):
        return {"$fraction": [value.numerator, value.denominator]}
    if isinstance(value, tuple):
        return {"$tuple": [encode_value(item) for item in value]}
    if isinstance(value, list):
        return [encode_value(item) for item in value]
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        if set(value) in ({"$fraction"}, {"$tuple"}):
            raise ValueError("reserved codec key")
        return {key: encode_value(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise ValueError("unsupported value type")

def decode_value(value):
    if isinstance(value, list):
        return [decode_value(item) for item in value]
    if isinstance(value, dict):
        if set(value) == {"$fraction"}:
            pair = value["$fraction"]
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError("invalid rational encoding")
            n, d = pair
            if any(isinstance(x, bool) or not isinstance(x, int) for x in pair) or d <= 0:
                raise ValueError("invalid rational components")
            fraction = Fraction(n, d)
            if (fraction.numerator, fraction.denominator) != (n, d):
                raise ValueError("noncanonical rational")
            return fraction
        if set(value) == {"$tuple"}:
            if not isinstance(value["$tuple"], list):
                raise ValueError("invalid tuple encoding")
            return tuple(decode_value(item) for item in value["$tuple"])
        return {key: decode_value(item) for key, item in value.items()}
    if value is None or isinstance(value, (str, bool, int)):
        return value
    raise ValueError("unsupported encoded value")

def canonical_json(value):
    return json.dumps(encode_value(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False)
