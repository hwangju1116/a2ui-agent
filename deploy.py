# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Main file for creating and managing A2UI agents on Agent Engine."""

import json
from google.protobuf import json_format

old_MessageToJson = json_format.MessageToJson
old_MessageToDict = json_format.MessageToDict

def is_pydantic_like(obj):
    # 프로토콜 버퍼 메시지는 반드시 'DESCRIPTOR' 속성을 가집니다.
    # DESCRIPTOR가 없고, dict나 json 변환 메서드를 가졌다면 Pydantic류 객체로 판단합니다.
    return not hasattr(obj, "DESCRIPTOR") and (
        hasattr(obj, "model_dump") or 
        hasattr(obj, "dict") or 
        hasattr(obj, "model_dump_json") or 
        hasattr(obj, "json") or
        type(obj).__name__ == "AgentCard"
    )

def new_MessageToJson(message, *args, **kwargs):
    if is_pydantic_like(message):
        if hasattr(message, "model_dump_json"):
            return message.model_dump_json()
        elif hasattr(message, "json"):
            return message.json()
        elif hasattr(message, "model_dump"):
            return json.dumps(message.model_dump())
        elif hasattr(message, "dict"):
            return json.dumps(message.dict())
    return old_MessageToJson(message, *args, **kwargs)

json_format.MessageToJson = new_MessageToJson

def new_MessageToDict(message, *args, **kwargs):
    if is_pydantic_like(message):
        if hasattr(message, "model_dump"):
            return message.model_dump()
        elif hasattr(message, "dict"):
            return message.dict()
    return old_MessageToDict(message, *args, **kwargs)

json_format.MessageToDict = new_MessageToDict

import os
import subprocess
import sys

project_root = os.path.dirname(os.path.abspath(__file__))
sdk_src_path = os.path.join(project_root, "libs", "a2ui-agent-sdk", "src")
if os.path.exists(sdk_src_path) and sdk_src_path not in sys.path:
    sys.path.insert(0, sdk_src_path)

from a2a.types import AgentSkill
from agent import SamsungAgent
import agent_executor
from dotenv import load_dotenv
from google.auth import default
from google.auth.transport.requests import Request
from google.genai import types
import httpx
import requests
import vertexai
from vertexai.preview.reasoning_engines import A2aAgent
from vertexai.preview.reasoning_engines.templates.a2a import create_agent_card

def _get_bearer_token():
  """Gets a bearer token for authenticating with Google Cloud."""
  try:
    credentials, _ = default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    request = Request()
    credentials.refresh(request)
    return credentials.token
  except Exception as e:  # pylint: disable=broad-except
    print(f"Error getting credentials: {e}")
    print(
        "Please ensure you have authenticated with 'gcloud auth "
        "application-default login'."
    )
  return None


def _register_agent_on_gemini_enterprise(
    project_id: str,
    app_id: str,
    agent_card: str,
    agent_name: str,
    display_name: str,
    description: str,
    agent_authorization: str | None = None,
):
  """Register or Update an Agent Engine to Gemini Enterprise."""
  api_endpoint = (
      f"https://discoveryengine.googleapis.com/v1alpha/projects/{project_id}/"
      f"locations/global/collections/default_collection/engines/{app_id}/"
      "assistants/default_assistant/agents"
  )

  # Get access token
  bearer_token = _get_bearer_token()

  # Prepare headers
  headers = {
      "Authorization": f"Bearer {bearer_token}",
      "Content-Type": "application/json",
      "X-Goog-User-Project": project_id,
  }

  # 1. List existing agents to see if one with the same display_name exists
  print("Checking for existing agents...")
  list_response = requests.get(api_endpoint, headers=headers)
  
  existing_agent_name = None
  if list_response.status_code == 200:
      agents_list = list_response.json().get("agents", [])
      for agent in agents_list:
          if agent.get("displayName") == display_name:
              existing_agent_name = agent.get("name")
              print(f"Found existing agent: {existing_agent_name}")
              break
  else:
      print(f"Warning: Failed to list agents ({list_response.status_code}). Proceeding with creation.")

  payload = {
      "displayName": display_name,
      "description": description,
      "a2aAgentDefinition": {"jsonAgentCard": agent_card},
  }

  if agent_authorization:
    payload["authorizationConfig"] = {"agentAuthorization": agent_authorization}

  if existing_agent_name:
      # 2. Update existing agent using PATCH
      print(f"Updating existing agent {existing_agent_name}...")
      # We need to use the full resource name in the URL
      update_url = f"https://discoveryengine.googleapis.com/v1alpha/{existing_agent_name}"
      
      # For PATCH, we usually need to specify updateMask.
      update_mask = "a2aAgentDefinition,description"
      if agent_authorization:
          update_mask += ",authorizationConfig"
          
      params = {"updateMask": update_mask}
      
      response = requests.patch(update_url, headers=headers, json=payload, params=params)
  else:
      # 3. Create new agent using POST
      print("Creating new agent...")
      payload["name"] = agent_name
      response = requests.post(api_endpoint, headers=headers, json=payload)

  if response.status_code in [200, 204]:
    print("✓ Agent registered/updated successfully!")
    return response.json() if response.status_code == 200 else {"name": existing_agent_name}
  print(f"✗ Registration/Update failed with status code: {response.status_code}")
  print(f"Response: {response.text}")
  response.raise_for_status()


def main():

  project_id = os.environ.get("PROJECT_ID")
  location = os.environ.get("LOCATION")
  storage = os.environ.get("STORAGE_BUCKET")
  
  # Auto-generate bucket name if missing or default
  if not storage or storage == "a2ui-bucket" or storage == "gs://a2ui-bucket":
      import uuid
      from datetime import datetime
      import dotenv
      
      date_str = datetime.now().strftime("%Y%m%d")
      unique_id = str(uuid.uuid4())[:8]
      storage = f"a2ui-agent-bucket-{date_str}-{unique_id}"
      print(f"Auto-generating unique bucket name: {storage}")
      
      # Update .env file
      dotenv.set_key(".env", "STORAGE_BUCKET", storage)
      print("✓ Updated .env file with new bucket name.")
      
      # Also update environment variable for current run
      os.environ["STORAGE_BUCKET"] = storage
      
  app_id = os.environ.get("GEMINI_ENTERPRISE_APP_ID")
  api_endpoint = f"{location}-aiplatform.googleapis.com"
  
  staging_bucket = storage
  if storage and not storage.startswith("gs://"):
      staging_bucket = f"gs://{storage}"

  if storage:
      print(f"Checking if storage bucket exists: {staging_bucket}")
      try:
          subprocess.run(["gcloud", "storage", "buckets", "describe", staging_bucket], check=True, capture_output=True)
          print(f"✓ Bucket {staging_bucket} exists.")
      except subprocess.CalledProcessError:
          print(f"Bucket {staging_bucket} does not exist. Creating it...")
          try:
              subprocess.run(["gcloud", "storage", "buckets", "create", staging_bucket, f"--location={location}"], check=True)
              print(f"✓ Bucket {staging_bucket} created successfully.")
          except subprocess.CalledProcessError as e:
              print(f"❌ Failed to create bucket: {e}")
              raise e

  vertexai.init(
      project=project_id,
      location=location,
      api_endpoint=api_endpoint,
      staging_bucket=staging_bucket,
  )

  print("✓ Vertex AI client initialized.")

  client = vertexai.Client(
      project=project_id,
      location=location,
      http_options=types.HttpOptions(
          api_version="v1beta1",
      ),
  )
  print("✓ Vertex AI client created.")

  agent_skill = AgentSkill(
      id="samsung_comparison",
      name="Samsung Comparison Tool",
      description="Helps compare Samsung products.",
      tags=["samsung", "comparison", "specs"],
      examples=[
          "Compare Galaxy S24 and S24+",
      ],
  )

  samsung_agent_card = create_agent_card(
      agent_name="Test Samsung Agent",
      description="A helpful assistant agent that can compare Samsung products.",
      skills=[agent_skill],
      streaming=False,
      default_input_modes=["text/plain"],
      default_output_modes=["text/plain"],
  )

  base_url = "http://0.0.0.0:8080"
  samsung_agent = SamsungAgent(base_url=base_url)

  print(f"✓ Samsung agent card created. {samsung_agent_card}")

  a2ui_agent = A2aAgent(
      agent_card=samsung_agent_card,
      agent_executor_builder=agent_executor.SamsungAgentExecutor,
  )
  a2ui_agent.set_up()

  print("✓ Local Samsung agent created.")

  config = {
      "display_name": "A2UI Samsung Agent on Agent Engine",
      "description": (
          "A helpful assistant agent that uses A2UI to render Samsung product comparisons."
      ),
      "agent_framework": "google-adk",
      "staging_bucket": staging_bucket,
      "gcs_dir_name": "v1",
      "requirements": [
          "google-cloud-aiplatform[agent_engines,adk]",
          "google-genai>=1.27.0",
          "python-dotenv>=1.1.0",
          "uvicorn",
          "a2a-sdk",
          "cloudpickle>=3.1.2",
          "pydantic",
          "jsonschema>=4.0.0",
          "google-cloud-firestore",
          "protobuf==4.25.3",
      ],
      "http_options": {
          "api_version": "v1beta1",
      },
      "max_instances": 1,
      "extra_packages": [
          "__init__.py",
          "agent_executor.py",
          "prompt_builder.py",
          "sample_samsung.json",
          "agent.py",
          "tools.py",
          "state_manager.py",
          "examples",
          "libs",
      ],
      "env_vars": {
          "NUM_WORKERS": "1",
          "PROJECT_ID": project_id,
          "LOCATION": location,
          "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
          "MODEL": "gemini-3.1-pro-preview"
      },
  }

  remote_agent = client.agent_engines.create(agent=a2ui_agent, config=config)

  remote_engine_resource = remote_agent.api_resource.name
  print(f"✓ Remote agent created. {remote_engine_resource}")

  a2a_endpoint = f"https://{api_endpoint}/v1beta1/{remote_engine_resource}/a2a/v1/card"
  bearer_token = _get_bearer_token()
  headers = {
      "Authorization": f"Bearer {bearer_token}",
      "Content-Type": "application/json",
  }

  print(f"✓ A2A endpoint: {a2a_endpoint}")

  response = httpx.get(a2a_endpoint, headers=headers)
  response.raise_for_status()
  a2ui_agent_card_json = response.json()
  
  # Add A2UI capabilities to the agent card.
  a2ui_agent_card_json["capabilities"] = {
      "streaming": False,
      "extensions": [{
          "uri": "https://a2ui.org/a2a-extension/a2ui/v0.8",
          "description": "Ability to render A2UI",
          "required": False,
          "params": {
              "supportedCatalogIds": [
                  "https://a2ui.org/specification/v0_8/standard_catalog_definition.json"
              ]
          },
      }],
  }
  a2ui_agent_card_str = json.dumps(a2ui_agent_card_json)

  print("✓ A2UI agent card fetched.")

  enterprise_agent = _register_agent_on_gemini_enterprise(
      project_id=project_id,
      app_id=app_id,
      agent_card=a2ui_agent_card_str,
      agent_name="a2ui_samsung_device_agent",
      display_name="A2UI Samsung Device Agent",
      description="A helpful assistant agent that uses A2UI to render Samsung product comparisons.",
      agent_authorization=os.environ.get("AGENT_AUTHORIZATION"),
  )

  print(enterprise_agent)
  print("≈" * 120)


if __name__ == "__main__":
  load_dotenv()
  main()
