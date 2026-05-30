#!/bin/bash

CLIENT_ID="YOUR_CLIENT_ID"
CLIENT_SECRET="YOUR_CLIENT_SECRET"

PROJECT_ID=$(gcloud config get-value project)
YOUR_AUTH_ID="a2ui-sample"

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