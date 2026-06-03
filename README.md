# Samsung Device Spec Comparison Agent

This project implements a spec comparison agent for Samsung products using **Google ADK** and **A2UI**, designed to be deployed on **Agent Runtime** and integrated with **Gemini Enterprise**.

## Setup and Deployment

### Prerequisites

-   Python 3.10+
-   `uv` package manager
-   Google Cloud SDK configured with your project

```bash
git clone https://github.com/hwangju1116/a2ui-agent
```

### 1. Authorization (OAuth)

To allow the agent to communicate with Gemini Enterprise, you need to register an authorization with the `cloud-platform` scope.

Open `generate_auth.sh` and update 'CLIENT_ID' and 'CLIENT_SECRET' by referring created OAuth credentials.

```bash
CLIENT_ID="YOUR_CLIENT_ID"
CLIENT_SECRET="YOUR_CLIENT_SECRET"
```

Run the deployment script:

```bash
cd a2ui-agent
chmod +x generate_auth.sh
./generate_auth.sh
```

### 2. Set Environment Variable to deploy.py

Open `deploy.py` and update 'GEMINI_ENTERPRISE_APP_ID' to your Gemini Enterprise App ID.

```bash
GEMINI_ENTERPRISE_APP_ID = "YOUR_APP_ID"
```

### 3. Deploy to Agent Runtime

Run the deployment script:

```bash
uv run deploy.py
```

This will output the `REASONING_ENGINE_ID`. Update your Web UI configuration or environment with this ID.

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

## License

Apache License 2.0
