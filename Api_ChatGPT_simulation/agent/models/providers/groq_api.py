# groq_api.py – DISABLED
#
# The Groq inference-platform API provider has been disabled.
# All models in this system are now accessed via browser automation.
#
# NOTE: "Groq" (inference platform) ≠ "Grok" (xAI chatbot at grok.com).
#       If you want xAI's Grok chatbot, use:  model="grok"
#
# Attempting to call this provider raises an explicit error.

def generate(messages=None, model=None, **kwargs):
    raise NotImplementedError(
        "The Groq API provider is disabled.\n"
        "All LLM access now goes through browser automation.\n"
        "Did you mean xAI's Grok chatbot? Use:  model='grok'"
    )