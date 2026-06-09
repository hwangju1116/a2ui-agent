#!/bin/bash

# ==============================================================================
# OAuth Credentials Template
# WARNING: NEVER commit your actual CLIENT_ID or CLIENT_SECRET to git!
# Keep them local and use this script only for manual registration.
# ==============================================================================

CLIENT_ID="YOUR_CLIENT_ID"
CLIENT_SECRET="YOUR_CLIENT_SECRET"

PROJECT_ID=$(gcloud config get-value project)

# This ID should match the AGENT_AUTHORIZATION value in your .env file
YOUR_AUTH_ID="product_oauth_v1"

if [ "$CLIENT_ID" = "YOUR_CLIENT_ID" ] || [ "$CLIENT_SECRET" = "YOUR_CLIENT_SECRET" ]; then
    echo "❌ Error: Please open generate_auth.sh and replace YOUR_CLIENT_ID and YOUR_CLIENT_SECRET with your actual Google OAuth credentials before running."
    exit 1
fi

echo "🚀 Registering OAuth Authorization '${YOUR_AUTH_ID}' for project '${PROJECT_ID}'..."

# ==========================================
# Create Authorization
# ==========================================
curl -X POST \
   -H "Authorization: Bearer $(gcloud auth print-access-token)" \
   -H "Content-Type: application/json" \
   -H "X-Goog-User-Project: ${PROJECT_ID}" \
   "https://global-discoveryengine.googleapis.com/v1alpha/projects/${PROJECT_ID}/locations/global/authorizations?authorizationId=${YOUR_AUTH_ID}" \
   -d "{
      \"name\": \"projects/${PROJECT_ID}/locations/global/authorizations/${YOUR_AUTH_ID}\",
      \"serverSideOauth2\": {
         \"clientId\": \"${CLIENT_ID}\",
         \"clientSecret\": \"${CLIENT_SECRET}\",
         \"authorizationUri\": \"https://accounts.google.com/o/oauth2/v2/auth?client_id=${CLIENT_ID}&redirect_uri=https%3A%2F%2Fvertexaisearch.cloud.google.com%2Fstatic%2Foauth%2Foauth.html&scope=https%3A%2F%2Fwww.googleapis.com%2Fauth%2Fcloud-platform&response_type=code&access_type=offline&prompt=consent\",
         \"tokenUri\": \"https://oauth2.googleapis.com/token\"
      }
   }"
