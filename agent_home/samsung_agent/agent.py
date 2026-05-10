import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from agent import samsung_agent_instance, VERSION_0_8
from google.adk.agents.llm_agent import LlmAgent
from google.genai import types
from a2ui_utils import a2ui_callback

class ProxyAgent(LlmAgent):
    def __init__(self):
        real_agent = samsung_agent_instance._ui_runners[VERSION_0_8].agent
        super().__init__(
            model=real_agent.model,
            name=real_agent.name,
            description=real_agent.description,
            instruction=real_agent.instruction,
            tools=real_agent.tools,
        )
        # Set the callback on the real agent
        real_agent.after_model_callback = a2ui_callback
        object.__setattr__(self, '_real_agent', real_agent)
        
    async def run_async(self, *args, **kwargs):
        print("--- PROXY: Delegating to real_agent.run_async ---")
        async for event in self._real_agent.run_async(*args, **kwargs):
            if event.is_final_response():
                print(f"--- PROXY: Final response event received. Metadata: {event.custom_metadata}")
            yield event

root_agent = ProxyAgent()
