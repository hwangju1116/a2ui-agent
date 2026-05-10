# Samsung Device Spec Comparison Agent

This project implements a spec comparison agent for Samsung products using **Google ADK** and **A2UI**, designed to be deployed on **Vertex AI Agent Engine** and integrated with **Gemini Enterprise**.

## Features

-   **Rich UI Interactions**: Uses A2UI to render product categories as vertical lists and product lists as horizontal carousels.
-   **Spec Comparison**: Compares specifications of selected products and presents them in a table format.
-   **State Management**: Simulates session history and maintains state across turns in a hybrid approach.

## Project Structure

-   `agent.py`: Core agent definition using Google ADK. Defines the tools and response handling.
-   `agent_executor.py`: Wrapper to intercept queries and manage session state for conversational context.
-   `tools.py`: Python functions exposed as tools to the agent (e.g., loading products, comparing specs).
-   `prompt_builder.py`: Constructs the system prompt for the model, guiding it on how to use A2UI templates.
-   `a2ui_utils.py`: Utility functions for handling A2UI interactions and parsing.
-   `state_manager.py`: Simple state management simulation (currently minimal).
-   `deploy.py`: Automation script to deploy the agent to Vertex AI Reasoning Engine and register it on Gemini Enterprise.
-   `examples/`: Directory containing JSON templates for A2UI components (Category List, Product List, Confirmation Dialog).
-   `sample_samsung.json`: Data file containing mock Samsung product specifications for comparison.

## What `deploy.py` Does

The `deploy.py` script automates the following steps:
1.  **Pre-check**: Verifies if the specified Google Cloud Storage bucket exists, and creates it if missing.
2.  **Package & Deploy**: Packages the local Python code and deploys it as a **Vertex AI Reasoning Engine** (Agent Engine).
3.  **Fetch Agent Card**: Calls the A2A endpoint of the deployed engine to fetch the generated `AgentCard` (skills definition).
4.  **Register on Gemini Enterprise**: Registers (or updates) the agent in the specified Gemini Enterprise App using the fetched Agent Card and provided Authorization resource.

## Setup and Deployment

### Prerequisites

-   Python 3.10+
-   `uv` package manager
-   Google Cloud SDK configured with your project

### 1. Environment Variables

Create a `.env` file in the root directory and fill in the following required values:

```env
PROJECT_ID=your-google-cloud-project-id
LOCATION=us-central1
STORAGE_BUCKET=your-bucket-name
GEMINI_ENTERPRISE_APP_ID=your-gemini-enterprise-app-id
AGENT_AUTHORIZATION=projects/YOUR_PROJECT_NUMBER/locations/global/authorizations/YOUR_AUTH_ID
```

-   **`PROJECT_ID`**: Your Google Cloud Project ID.
-   **`LOCATION`**: The region for Vertex AI (e.g., `us-central1`).
-   **`STORAGE_BUCKET`**: The GCS bucket name used for staging agent artifacts. If the bucket does not exist, `deploy.py` will attempt to create it automatically.
-   **`GEMINI_ENTERPRISE_APP_ID`**: The ID of your Gemini Enterprise App (Engine) where the agent will be registered.
-   **`AGENT_AUTHORIZATION`**: The resource path for OAuth authorization (needed if the agent calls external authenticated tools).

### 2. Authorization (OAuth)

To allow the agent to communicate with Gemini Enterprise, you need to register an authorization with the `cloud-platform` scope.

Run the following command, replacing placeholders with your values:

```bash
curl -X POST \
   -H "Authorization: Bearer $(gcloud auth print-access-token)" \
   -H "Content-Type: application/json" \
   -H "X-Goog-User-Project: YOUR_PROJECT_ID" \
   "https://global-discoveryengine.googleapis.com/v1alpha/projects/YOUR_PROJECT_ID/locations/global/authorizations?authorizationId=YOUR_AUTH_ID" \
   -d '{
      "name": "projects/YOUR_PROJECT_ID/locations/global/authorizations/YOUR_AUTH_ID",
      "serverSideOauth2": {
         "clientId": "YOUR_CLIENT_ID",
         "clientSecret": "YOUR_CLIENT_SECRET",
         "authorizationUri": "https://accounts.google.com/o/oauth2/v2/auth?client_id=YOUR_CLIENT_ID&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&response_type=code&access_type=offline&prompt=consent",
         "tokenUri": "https://oauth2.googleapis.com/token"
      }
   }'
```

### 3. Deploy to Agent Engine

Run the deployment script:

```bash
uv run deploy.py
```

This will output the `REASONING_ENGINE_ID`. Update your Web UI configuration or environment with this ID.

## License

Apache License 2.0
