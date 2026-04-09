# ai.py
import anthropic
import json
import time
from knowledge_base import load_knowledge_base


def generate_questions(api_key: str, topic: str, count: int, asked_questions: list = None) -> list:
    """
    Use Anthropic Claude to generate fresh multiple choice quiz questions.
    Injects SpaceComputer knowledge base and avoids previously asked questions.
    """
    if asked_questions is None:
        asked_questions = []

    client = anthropic.Anthropic(api_key=api_key)

    # Load knowledge base
    kb = load_knowledge_base()
    if kb:
        kb_section = f"""Use the following official SpaceComputer documentation and content as your PRIMARY source for generating questions. Base your questions on facts from this content:

{kb[:50000]}

"""
        print(f"[AI] Knowledge base loaded — {len(kb)} chars")
    else:
        kb_section = ""
        print("[AI] No knowledge base found — run knowledge_base.py to build one")

    # Build avoid section
    avoid_section = ""
    if asked_questions:
        recent = asked_questions[:200]
        avoid_list = "\n".join(f"- {q}" for q in recent)
        avoid_section = f"""
IMPORTANT — Do NOT repeat or rephrase any of these previously asked questions:
{avoid_list}

"""

    prompt = f"""{kb_section}{avoid_section}Generate {count} multiple choice quiz questions about: {topic}.

Rules:
- Base questions on the SpaceComputer documentation provided above
- Each question must be factually accurate and specific to SpaceComputer
- Each question must have exactly 4 answer options labeled A, B, C, D
- Only one answer is correct
- Questions should range from easy to hard
- Every question must be unique and different from the avoid list

Return ONLY a valid JSON array with no extra text, no markdown, no backticks. Format:
[
  {{
    "question": "Question text here?",
    "options": {{
      "A": "Option A text",
      "B": "Option B text",
      "C": "Option C text",
      "D": "Option D text"
    }},
    "answer": "A",
    "explanation": "Brief explanation of why this is correct"
  }}
]"""

    last_error = None
    for attempt in range(2):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                messages=[{"role": "user", "content": prompt}],
                temperature=1,
                max_tokens=6000
            )

            raw = response.content[0].text.strip()

            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            questions = json.loads(raw)
            return questions

        except Exception as e:
            last_error = e
            if attempt == 0:
                print(f"[AI] Attempt 1 failed: {e} — retrying in 2s...")
                time.sleep(2)

    raise last_error