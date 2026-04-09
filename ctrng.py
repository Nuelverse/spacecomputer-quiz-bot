# ctrng.py
import requests
import json
import random


def get_cosmic_random(config) -> dict:
    """
    Fetch a random value from SpaceComputer's cTRNG IPFS beacon.
    Tries multiple gateways. Returns seed and metadata.
    """
    for gateway in config.CTRNG_IPFS_GATEWAYS:
        try:
            response = requests.get(gateway, timeout=15)
            response.raise_for_status()
            data = response.json()

            # Parse the actual beacon format:
            # { "data": { "ctrng": ["hex1", "hex2", "hex3"], "sequence": N, "timestamp": N } }
            ctrng_values = data.get("data", {}).get("ctrng", [])
            sequence = data.get("data", {}).get("sequence", 0)
            timestamp = data.get("data", {}).get("timestamp", 0)

            if ctrng_values:
                # Combine all 3 cosmic readings into one seed
                combined_hex = "".join(ctrng_values)
                seed = int(combined_hex[:15], 16)  # use first 15 hex chars as integer seed

                print(f"[cTRNG] ✅ Live cosmic seed: {seed}")
                print(f"[cTRNG] Sequence: #{sequence} | Timestamp: {timestamp}")
                print(f"[cTRNG] Raw values: {ctrng_values[0][:16]}...")

                return {
                    "seed": seed,
                    "sequence": sequence,
                    "timestamp": timestamp,
                    "raw": ctrng_values,
                    "source": f"SpaceComputer cTRNG (cosmic radiation via satellite) — pulse #{sequence}"
                }

        except Exception as e:
            print(f"[cTRNG] Gateway failed ({gateway[:40]}...): {e}")
            continue

    # All gateways failed — use fallback
    print("[cTRNG] ⚠️ All gateways failed. Using fallback randomness.")
    fallback_seed = random.randint(0, 10 ** 15)
    return {
        "seed": fallback_seed,
        "sequence": None,
        "timestamp": None,
        "raw": None,
        "source": "fallback (cTRNG unavailable)"
    }


def cosmic_shuffle(items: list, seed: int) -> list:
    """Shuffle a list using a cosmic random seed."""
    rng = random.Random(seed)
    shuffled = items.copy()
    rng.shuffle(shuffled)
    return shuffled


def cosmic_choice(items: list, seed: int):
    """Pick one item from a list using a cosmic random seed."""
    rng = random.Random(seed)
    return rng.choice(items)