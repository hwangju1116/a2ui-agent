# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import logging
from typing import Dict, Optional
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
sdk_src_path = os.path.join(project_root, "libs", "a2ui-agent-sdk", "src")
if os.path.exists(sdk_src_path) and sdk_src_path not in sys.path:
    sys.path.insert(0, sdk_src_path)

from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Part,
    TextPart,
)
from a2ui.a2a.extension import get_a2ui_agent_extension
from a2ui.a2a.parts import parse_response_to_parts
from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.parser.parser import parse_response
from a2ui.schema.common_modifiers import remove_strict_validation
from a2ui.schema.constants import A2UI_CLOSE_TAG, A2UI_OPEN_TAG, VERSION_0_8
from a2ui.schema.manager import A2uiSchemaManager
import dotenv
from google.adk.agents import run_config
from google.adk.agents.llm_agent import LlmAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory import VertexAiMemoryBankService
from google.adk.sessions import VertexAiSessionService
from google.adk.runners import Runner
from google.genai import types
import jsonschema
from prompt_builder import ROLE_DESCRIPTION, UI_DESCRIPTION, WORKFLOW_DESCRIPTION, get_text_prompt
from tools import get_categories, get_products_by_category, get_product_details, compare_products, save_selection

SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

dotenv.load_dotenv()
logger = logging.getLogger(__name__)

class SamsungAgent:
  """An agent that compares Samsung products."""

  def __init__(self, base_url: str):
    self.base_url = base_url
    self._agent_name = "samsung_agent"
    self._user_id = "remote_agent"
    self._text_runner: Optional[Runner] = self._build_runner(self._build_llm_agent())

    self._schema_managers: Dict[str, A2uiSchemaManager] = {}
    self._ui_runners: Dict[str, Runner] = {}

    # Gemini Enerprise only supports VERSION_0_8 for now.
    for version in [VERSION_0_8]:
      schema_manager = self._build_schema_manager(version)
      self._schema_managers[version] = schema_manager
      agent = self._build_llm_agent(schema_manager)
      self._ui_runners[version] = self._build_runner(agent)

    self._agent_card = self._build_agent_card()

  @property
  def agent_card(self) -> AgentCard:
    return self._agent_card

  def _build_schema_manager(self, version: str) -> A2uiSchemaManager:
    return A2uiSchemaManager(
        version=version,
        catalogs=[
            BasicCatalog.get_config(
                version=version,
                examples_path=os.path.join(
                    os.path.dirname(__file__), f"examples/{version}"
                ),
            )
        ],
        schema_modifiers=[remove_strict_validation],
    )

  def _build_agent_card(self) -> AgentCard:
    extensions = []
    if self._schema_managers:
      for version, sm in self._schema_managers.items():
        ext = get_a2ui_agent_extension(
            version,
            sm.accepts_inline_catalogs,
            sm.supported_catalog_ids,
        )
        extensions.append(ext)

    capabilities = AgentCapabilities(
        streaming=False,
        extensions=extensions,
    )
    skill = AgentSkill(
        id="samsung_comparison",
        name="Samsung Comparison Tool",
        description="Helps compare Samsung products.",
        tags=["samsung", "comparison", "specs"],
        examples=["Compare Galaxy S24 and S24+"],
    )

    return AgentCard(
        name="Samsung Agent",
        description=(
            "This agent helps compare Samsung products based on user criteria."
        ),
        url=self.base_url,
        version="1.0.0",
        default_input_modes=SUPPORTED_CONTENT_TYPES,
        default_output_modes=SUPPORTED_CONTENT_TYPES,
        capabilities=capabilities,
        preferred_transport="HTTP+JSON",
        skills=[skill],
    )

  def _build_runner(self, agent: LlmAgent) -> Runner:
    project_id = os.environ.get("PROJECT_ID")
    location = os.environ.get("LOCATION")
    
    # Find the latest engine ID dynamically
    from vertexai.preview import reasoning_engines
    import vertexai
    vertexai.init(project=project_id, location=location)
    
    engine_id = "default_engine"
    try:
        engines = reasoning_engines.ReasoningEngine.list()
        samsung_engines = [e for e in engines if e.display_name == "A2UI Samsung Agent on Agent Engine"]
        
        if samsung_engines:
            # Pick the first one (assuming list returns latest first or after cleanup only few left)
            engine_id = samsung_engines[0].resource_name.split("/")[-1]
            print(f"--- Found current engine ID for Memory Bank: {engine_id}")
    except Exception as e:
        print(f"--- Failed to list engines or find ID: {e}. Using default_engine.")
    
    return Runner(
        app_name=self._agent_name,
        agent=agent,
        artifact_service=InMemoryArtifactService(),
        session_service=VertexAiSessionService(project=project_id, location=location, agent_engine_id=engine_id),
        memory_service=VertexAiMemoryBankService(project=project_id, location=location, agent_engine_id=engine_id),
    )

  def get_processing_message(self) -> str:
    return "Searching for Samsung products..."

  def _build_llm_agent(
      self, schema_manager: Optional[A2uiSchemaManager] = None
  ) -> LlmAgent:
    instruction = (
        schema_manager.generate_system_prompt(
            role_description=ROLE_DESCRIPTION,
            workflow_description=WORKFLOW_DESCRIPTION,
            ui_description=UI_DESCRIPTION,
            include_schema=True,
            include_examples=True,
            validate_examples=True,
        )
        if schema_manager
        else get_text_prompt()
    )

    os.environ["GOOGLE_CLOUD_LOCATION"] = os.environ.get("LOCATION", "us-central1")
    return LlmAgent(
        model=os.getenv("MODEL", "gemini-3.1-pro-preview"),
        name=self._agent_name,
        description="An agent that compares Samsung products.",
        instruction=instruction,
        tools=[get_categories, get_products_by_category, get_product_details, compare_products, save_selection],
    )

  async def fetch_response(
      self, query, session_id, ui_version: Optional[str] = None
  ) -> list[Part]:
    session_state = {"base_url": self.base_url}

    if ui_version:
      runner = self._ui_runners[ui_version]
      schema_manager = self._schema_managers[ui_version]
      selected_catalog = (
          schema_manager.get_selected_catalog() if schema_manager else None
      )
    else:
      runner = self._text_runner
      selected_catalog = None

    session = await runner.session_service.get_session(
        app_name=self._agent_name,
        user_id=self._user_id,
        session_id=session_id,
    )
    if session is None:
      session = await runner.session_service.create_session(
          app_name=self._agent_name,
          user_id=self._user_id,
          state=session_state,
          session_id=session_id,
      )
    elif "base_url" not in session.state:
      session.state["base_url"] = self.base_url

    # Rely on default session state

    max_retries = 1
    attempt = 0
    current_query_text = query

    if ui_version and (not selected_catalog or not selected_catalog.catalog_schema):
      logger.error(
          "--- SamsungAgent.fetch_response: A2UI_SCHEMA is not loaded. "
          "Cannot perform UI validation. ---"
      )
      return [
          Part(
              root=TextPart(
                  text=(
                      "I'm sorry, I'm facing an internal configuration"
                      " error with my UI components. Please contact"
                      " support."
                  )
              )
          )
      ]

    while attempt <= max_retries:
      attempt += 1
      logger.info(
          "--- SamsungAgent.fetch_response: Attempt"
          f" {attempt}/{max_retries + 1} for session {session_id} ---"
      )

      current_message = types.Content(
          role="user", parts=[types.Part.from_text(text=current_query_text)]
      )

      full_content_list = []

      try:
        async for event in runner.run_async(
            user_id=self._user_id,
            session_id=session.id,
            new_message=current_message,
        ):
          if event.is_final_response():
            if event.content and event.content.parts and event.content.parts[0].text:
              full_content_list.extend([p.text for p in event.content.parts if p.text])
      except Exception as e:
        logger.error(
            "--- SamsungAgent.fetch_response: Exception caught while running"
            f" runner: {e} ---"
        )
        raise e

      final_response_content = "".join(full_content_list)

      if final_response_content is None:
        if attempt <= max_retries:
          current_query_text = (
              "I received no response. Please try again."
              f"Please retry the original request: '{query}'"
          )
          continue
        else:
          final_response_content = (
              "I'm sorry, I encountered an error and couldn't process your request."
          )

      is_valid = False
      error_message = ""

      if ui_version:
        try:
          response_parts = parse_response(final_response_content)

          for part in response_parts:
            if not part.a2ui_json:
              continue

            parsed_json_data = part.a2ui_json

            if parsed_json_data == []:
              is_valid = True
            else:
              selected_catalog.validator.validate(parsed_json_data)
              is_valid = True
        except (
            ValueError,
            json.JSONDecodeError,
            jsonschema.exceptions.ValidationError,
        ) as e:
          logger.warning(
              f"--- SamsungAgent.fetch_response: A2UI validation failed: {e}"
              f" (Attempt {attempt}) ---"
          )
          print(f"--- FAILED JSON CONTENT ---\n{final_response_content}\n-------------------")
          error_message = f"Validation failed: {e}."

      else:
        is_valid = True

      if is_valid:
        # Save conversation history to state
        history = session.state.get("conversation_history", [])
        history.append({"user": query, "agent": final_response_content})
        session.state["conversation_history"] = history
        return parse_response_to_parts(final_response_content)

      if attempt <= max_retries:
        current_query_text = (
            f"Your previous response was invalid. {error_message} You MUST"
            " generate a valid response that strictly follows the A2UI JSON"
            " SCHEMA. The response MUST be a JSON list of A2UI messages."
            f" Ensure each JSON part is wrapped in '{A2UI_OPEN_TAG}' and"
            f" '{A2UI_CLOSE_TAG}' tags. Please retry the original request:"
            f" '{query}'"
        )

    return [
        Part(
            root=TextPart(
                text=(
                    "I'm sorry, I'm having trouble generating the interface"
                    " for that request right now. Please try again in a"
                    " moment."
                )
            )
        )
    ]

# ADK web looks for 'root_agent' in this file.
root_agent = SamsungAgent("http://0.0.0.0:8080")
