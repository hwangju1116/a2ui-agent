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
GEMINI_ENTERPRISE_APP_ID = "[본인의_GEMINI_ENTERPRISE_APP_ID]"


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

import a2a
import shutil
from a2a.types import AgentSkill
from agent import ProductAgent
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

import google.auth
from google.cloud import resourcemanager_v3
def main():
  import os
  credentials, PROJECT_ID = google.auth.default()
  client = resourcemanager_v3.ProjectsClient(credentials=credentials)
  project_info = client.get_project(name=f"projects/{PROJECT_ID}")
  project_number = project_info.name.split("/")[-1]
  project_id = PROJECT_ID
  location = "us-central1"
  storage = f"{PROJECT_ID}-a2ui-bucket"
  import sys
  app_id = GEMINI_ENTERPRISE_APP_ID
  if not app_id or app_id == "YOUR_APP_ID" or "[본인의" in app_id:
      print("❌ Error: GEMINI_ENTERPRISE_APP_ID is not configured.")
      print("Please configure GEMINI_ENTERPRISE_APP_ID in your .env file.")
      print("Example: GEMINI_ENTERPRISE_APP_ID=a2ui-test-app_1777477684577")
      sys.exit(1)

  authorization = f"projects/{project_number}/locations/global/authorizations/a2ui-sample"
  if not authorization:
      print("❌ Error: AGENT_AUTHORIZATION is not configured.")
      print("Please configure AGENT_AUTHORIZATION in your .env file with your full OAuth authorization path.")
      print("Example: AGENT_AUTHORIZATION=projects/380375295054/locations/global/authorizations/product_oauth_v1")
      sys.exit(1)
  
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
      id="product_comparison",
      name="Product Comparison Tool",
      description="Helps compare products.",
      tags=["product", "comparison", "specs"],
      examples=[
          "Compare iPhone 16 and Galaxy S25",
      ],
  )

  product_agent_card = create_agent_card(
      agent_name="Test Product Agent",
      description="A helpful assistant agent that can compare products.",
      skills=[agent_skill],
      streaming=False,
      default_input_modes=["text/plain"],
      default_output_modes=["text/plain"],
  )

  base_url = "http://0.0.0.0:8080"
  product_agent = ProductAgent(base_url=base_url)

  print(f"✓ Product agent card created. {product_agent_card}")

  a2ui_agent = A2aAgent(
      agent_card=product_agent_card,
      agent_executor_builder=agent_executor.ProductAgentExecutor,
  )
  a2ui_agent.set_up()

  print("✓ Local Product Comparison agent created.")

  config = {
      "display_name": "A2UI Product Agent on Agent Engine",
      "description": (
          "A helpful assistant agent that uses A2UI to render product comparisons."
      ),
      "agent_framework": "google-adk",
      "staging_bucket": staging_bucket,
      "gcs_dir_name": "v1",
      "requirements": [
          "google-cloud-aiplatform[agent_engines,adk]",
          "google-genai>=1.27.0",
          "python-dotenv>=1.1.0",
          "uvicorn",
          "cloudpickle>=3.1.2",
          "pydantic",
          "jsonschema>=4.0.0",
          "google-cloud-firestore",
          "a2ui-agent-sdk==0.1.2",
          "a2a-sdk==0.3.25",
          "starlette==0.52.1",
          "sse-starlette==3.4.4",
      ],
      "http_options": {
          "api_version": "v1beta1",
      },
      "max_instances": 1,
      "extra_packages": [
          "__init__.py",
          "agent_executor.py",
          "prompt_builder.py",
          "agent.py",
          "tools.py",
          "examples",
      ],
      "env_vars": {
          "NUM_WORKERS": "1",
          "PROJECT_ID": project_id,
          "LOCATION": location,
          "GOOGLE_GENAI_USE_VERTEXAI": "TRUE",
          "MODEL": os.environ.get("MODEL", "gemini-3.1-pro-preview")
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
      agent_name="a2ui_product_comparison_agent",
      display_name="A2UI Product Comparison Agent",
      description="A helpful assistant agent that uses A2UI to render product comparisons.",
      agent_authorization=authorization,
  )

  print(enterprise_agent)
  print("≈" * 120)


if __name__ == "__main__":
  load_dotenv()
  main()
