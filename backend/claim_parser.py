# backend/claim_parser.py (new file)
import re

def split_compound_claim(claim: str) -> list:
    """
    Splits compound claims into atomic sub-claims.
    Example: "Iran lost the war and Russia surrendered"
    → ["Iran lost the war", "Russia surrendered"]
    """
    # Split on " and ", " but ", ". "
    separators = [" and ", " but ", " while ", ". ", "; "]
    parts = [claim]
    for sep in separators:
        new_parts = []
        for part in parts:
            split = part.split(sep)
            if len(split) > 1 and all(len(s.strip()) > 10 for s in split):
                new_parts.extend([s.strip() for s in split])
            else:
                new_parts.append(part)
        parts = new_parts
    return [p for p in parts if len(p.strip()) > 5]


def is_compound(claim: str) -> bool:
    return len(split_compound_claim(claim)) > 1


if __name__ == "__main__":
    test = "Iran lost the war and Russia surrendered"
    parts = split_compound_claim(test)
    print(f"Compound: {is_compound(test)}")
    print(f"Parts: {parts}")
