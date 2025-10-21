#!/bin/bash

# Configuration
PROJECT_ID="model-sphere-474807-r6"
SERVICE_NAME="coherence-tutor"
REGION="asia-southeast1"
REPOSITORY="coherence-tutor"

echo "🚀 Deploying Coherence AI Tutor to Google Cloud Run..."

# Set project
gcloud config set project $PROJECT_ID

# Build and deploy in one step (simpler for Cloud Run)
echo "📦 Building and deploying..."
gcloud run deploy $SERVICE_NAME \
  --source . \
  --region=$REGION \
  --allow-unauthenticated \
  --port=8080 \
  --memory=1Gi \
  --cpu=1 \
  --timeout=300 \
  --max-instances=10 \
  --min-instances=0 \
  --set-secrets="FLASK_SECRET_KEY=FLASK_SECRET_KEY:latest,JWT_SECRET=JWT_SECRET:latest,GEMINI_API_KEY=GEMINI_API_KEY:latest,DB_PASSWORD=DB_PASSWORD:latest" \
  --env-vars-file=env.yaml

if [ $? -ne 0 ]; then
  echo "❌ Deployment failed! Check logs:"
  echo "gcloud run services logs read $SERVICE_NAME --region=$REGION --limit=50"
  exit 1
fi

echo "✅ Deployment complete!"
echo "🔗 Service URL:"
gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)"

echo ""
echo "📊 Test endpoints:"
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)")
echo "Health: curl $SERVICE_URL/health"
echo "Admin:  $SERVICE_URL/admin?token=YOUR_TOKEN"