# knowledge_base.py
# Run this script to fetch and update SpaceComputer's knowledge base
# Re-run whenever SpaceComputer publishes new content

import requests
import os
import re
import time

KB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "knowledge_base.txt")

SOURCES = [
    # Docs
    "https://docs.spacecomputer.io/",
    # Main site
    "https://spacecomputer.io",
    # Blog posts
    "https://blog.spacecomputer.io/orbitport-gateway-to-space/",
    "https://blog.spacecomputer.io/randomness-as-infrastructure/",
    "https://blog.spacecomputer.io/verifying-true-randomness-in-cryptographic-systems/",
    "https://blog.spacecomputer.io/kms-beyond-cloud/",
    "https://blog.spacecomputer.io/decentralized-smallsats-matter/",
    "https://blog.spacecomputer.io/space-tech-ecosystem/",
    "https://blog.spacecomputer.io/2026-the-road-ahead/",
    "https://blog.spacecomputer.io/spacecomputer-datahaven-partnership/",
    "https://blog.spacecomputer.io/2025-in-review-orbital-foundations/",
    "https://blog.spacecomputer.io/spacecomputer-raises-10m-to-bring-trusted-execution-to-orbit-merge-cryptography-satellites-and-confidential-smart-contracts/",
    "https://blog.spacecomputer.io/spacecomputer-partners-with-eigencloud-data-availability-for-the-orbital-world-computer/",
    "https://blog.spacecomputer.io/cypherpunk-cosmic-randomness-ctrng-beta-now-live/",
    "https://blog.spacecomputer.io/why-trust-belongs-in-orbit-satellite-based-tees/",
    "https://blog.spacecomputer.io/spacecomputer-mission-and-technical-vision/",
    "https://blog.spacecomputer.io/spacecomputer-providing-reliable-true-randomness-from-the-tamper-proof-decentralized-orbital-network/",
    "https://blog.spacecomputer.io/generating-secure-nonces-for-sign-in-with-ethereum-using-verifiable-cosmic-randomness-from-space/",
    "https://blog.spacecomputer.io/generating-secure-passwords-with-verifiable-randomness-from-space/",
    "https://blog.spacecomputer.io/cooling-for-orbital-compute/",
    "https://blog.spacecomputer.io/building-with-spacecomputer-orbitport-a-guide-to-cosmic-randomness-in-web3/",
]


def clean_text(html_text: str) -> str:
    """Strip HTML tags and clean up whitespace."""
    # Remove script and style blocks
    html_text = re.sub(r'<script[^>]*>.*?</script>', '', html_text, flags=re.DOTALL)
    html_text = re.sub(r'<style[^>]*>.*?</style>', '', html_text, flags=re.DOTALL)
    # Remove HTML tags
    html_text = re.sub(r'<[^>]+>', ' ', html_text)
    # Decode common HTML entities
    html_text = html_text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&nbsp;', ' ').replace('&#39;', "'").replace('&quot;', '"')
    # Collapse whitespace
    html_text = re.sub(r'\s+', ' ', html_text).strip()
    return html_text


def fetch_page(url: str) -> str:
    """Fetch a page and return cleaned text content."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SpaceComputerQuizBot/1.0)"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        cleaned = clean_text(response.text)
        # Limit each source to 3000 chars to keep total size manageable
        return cleaned[:3000]
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return ""


def build_knowledge_base() -> dict:
    """Fetch all sources and save to knowledge_base.txt. Returns a summary dict."""
    print(f"\n🛰️ Building SpaceComputer Knowledge Base")
    print(f"{'─'*50}")

    all_content = []
    all_content.append("=== SPACECOMPUTER KNOWLEDGE BASE ===\n")
    all_content.append("This document contains official SpaceComputer content used to generate quiz questions.\n\n")

    fetched = 0
    for url in SOURCES:
        print(f"Fetching: {url}")
        content = fetch_page(url)
        if content:
            all_content.append(f"\n--- SOURCE: {url} ---\n")
            all_content.append(content)
            all_content.append("\n")
            print(f"  ✅ {len(content)} chars")
            fetched += 1
        time.sleep(0.5)  # be polite to the server

    full_text = "\n".join(all_content)

    with open(KB_PATH, "w", encoding="utf-8") as f:
        f.write(full_text)

    size_kb = os.path.getsize(KB_PATH) / 1024
    print(f"\n{'─'*50}")
    print(f"✅ Knowledge base saved to: {KB_PATH}")
    print(f"   Size: {size_kb:.1f} KB | Sources: {fetched}/{len(SOURCES)}")
    print(f"\nRe-run this script whenever SpaceComputer publishes new content.")

    return {"sources_fetched": fetched, "sources_total": len(SOURCES), "size_kb": size_kb}


def load_knowledge_base() -> str:
    """Load the knowledge base text. Returns empty string if not found."""
    if not os.path.exists(KB_PATH):
        return ""
    with open(KB_PATH, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    build_knowledge_base()
