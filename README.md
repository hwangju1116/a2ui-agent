# Universal Product Spec Comparison Agent (A2UI)

This project implements a brand-agnostic product search, details lookup, and specification comparison agent using **Google ADK** and **A2UI**. It is designed to be deployed on **Vertex AI Reasoning Engine** (Agent Engine) and seamlessly integrated with **Gemini Enterprise**.

Instead of relying on static mock data, this agent dynamically leverages **Google Search Grounding** to fetch real-time, accurate specifications and verified official URLs for products in any category (e.g., smartphones, laptops, TVs, home appliances).

---

## Features

-   **Dynamic Web Search (Google Search Grounding)**: Dynamically searches the web to find the latest 2025/2026 models, specs, and prices for any product category.
-   **Link Grounding (No 404s)**: Strictly validates and extracts only official, verified product URLs. If a verified link isn't found, it safely excludes "Buy Now" links from the comparison table to prevent broken 404 links.
-   **Rich UI Interactions**: Uses A2UI (Agent-to-User Interface) to render:
    -   **Category List**: A compact, vertical card list (strictly constrained to 80px height for optimal screen space).
    -   **Product List**: A clean, horizontal carousel with fixed `200x200 px` square cards.
    -   **Comparison Table**: A detailed, structured markdown table comparing key specifications (Processor, Display, Camera, Battery, Memory/Storage, Price, and Links).
-   **Independent Surfaces**: Renders categories and product lists on separate, dedicated UI surfaces (`category-modal` and `product-modal`) so that the conversation history flows naturally without overwriting previous selections.
-   **Dynamic Model Configuration**: Easily switch underlying Gemini models (e.g., `gemini-3.5-flash`, `gemini-3.1-pro-preview`) via environment variables.

---

## Setup and Configuration

### Prerequisites

-   Python 3.10+
-   `uv` package manager (recommended)
-   Google Cloud SDK configured with your active billing project
-   Authorized credentials with Google Cloud (`gcloud auth login`, `gcloud auth application-default login`)

### 1. Environment Variables (`.env`)

Create a `.env` file in the root directory and configure your project and model settings. **Never commit this file to version control.**

```env
PROJECT_ID="your-google-cloud-project-id"
LOCATION="us-central1"
AGENT_AUTHORIZATION="product_oauth_v1"
MODEL="gemini-3.5-flash"
```

-   `PROJECT_ID`: Your Google Cloud Project ID.
-   `LOCATION`: Google Cloud region (default is `us-central1`).
-   `AGENT_AUTHORIZATION`: The ID of the OAuth Authorization resource registered in Gemini Enterprise.
-   `MODEL`: The Gemini model to use for the agent and tools (e.g., `gemini-3.5-flash` for fast, cost-effective reasoning).

### 2. Register OAuth Authorization

To allow the agent to securely communicate with Gemini Enterprise, you must register an OAuth Authorization resource.

We provide a template script `generate_auth.sh` (with secrets removed). Copy the template, fill in your OAuth Client credentials, and run it:

```bash
# Edit generate_auth.sh with your Client ID & Secret (do NOT commit these changes!)
./generate_auth.sh
```

---

## Local Development & Testing

We provide a `Makefile` with shortcut commands to simplify development:

### Run the Agent Locally

You can test the agent's reasoning and A2UI JSON payload generation locally before deploying it to Google Cloud:

```bash
make run
```

This executes `test_locally.py` in UI mode, simulating a two-turn conversation (greeting ➔ category selection) and printing the exact generated A2UI JSON to the console for inspection.

---

## Deployment to Vertex AI

Once local testing is successful, deploy the agent to the cloud:

```bash
make deploy
```

### What `make deploy` does under the hood:
1.  **Packages Code**: Bundles the local Python files (`agent.py`, `agent_executor.py`, `tools.py`, `prompt_builder.py`) and the A2UI templates in the `examples/` folder.
2.  **Deploys to Vertex AI**: Registers the agent as a **Vertex AI Reasoning Engine** and uploads it to Google Cloud.
3.  **Registers on Gemini Enterprise**: Automatically registers/updates the agent on your Gemini Enterprise App instance, binding it to the configured OAuth Authorization.

---

## Project Structure

-   [agent.py](file:///Users/hwangju/.gemini/jetski/scratch/a2ui-agent/agent.py): Core agent definition using Google ADK. Orchestrates prompts and tools.
-   [agent_executor.py](file:///Users/hwangju/.gemini/jetski/scratch/a2ui-agent/agent_executor.py): Intercepts user queries, manages conversation history, and handles A2UI state transitions.
-   [tools.py](file:///Users/hwangju/.gemini/jetski/scratch/a2ui-agent/tools.py): Python tools exposed to the model, including Google Search Grounding for live product specs and comparison generation.
-   [prompt_builder.py](file:///Users/hwangju/.gemini/jetski/scratch/a2ui-agent/prompt_builder.py): Constructs the system instructions, strictly enforcing UI layout dimensions (80px category cards, 200x200px product cards) and link grounding rules.
-   [examples/0.8/](file:///Users/hwangju/.gemini/jetski/scratch/a2ui-agent/examples/0.8/): Contains A2UI JSON schema templates used by the model to render UI components:
    -   `product_category_list.json`: Template for the compact vertical category list.
    -   `product_list.json`: Template for the horizontal product carousel.
    -   `product_confirm.json`: Template for the product selection confirmation dialog.
-   [test_locally.py](file:///Users/hwangju/.gemini/jetski/scratch/a2ui-agent/test_locally.py): Local simulation script to verify multi-turn A2UI flows.

---

## License

Apache License 2.0
