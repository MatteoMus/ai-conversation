import re

def extract_reasoning(text: str) -> str:
    # Try to find reasoning tag
    reasoning_match = re.search(r'<reasoning>(.*?)</reasoning>', text, re.DOTALL)
    if reasoning_match:
        return reasoning_match.group(1).strip()
    
    # If no reasoning tag, extract everything outside <STOP>...</STOP>
    outside_text = re.sub(r'<STOP>.*?</STOP>', '', text, flags=re.DOTALL).strip()
    return outside_text

# Example usage
sample_text = """
<STOP>true</STOP>
  The discussion has reached a meaningful conclusion as the agents have comprehensively explored the topics of wars, technology, pollution, and societal concerns. They have discussed the potential for technological innovations to mitigate environmental impacts, raised critical perspectives on these solutions, and proposed strategies to overcome practical challenges. The conversation has naturally transitioned to closure, with the agents summarizing their thoughts and expressing final reflections on the complexities and possibilities of implementing technological solutions in conflict zones
"""

print(extract_reasoning(sample_text))
