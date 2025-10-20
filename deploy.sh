#!/bin/bash

# Configuration
PROJECT_ID="model-sphere-474807-r6"
SERVICE_NAME="coherence-tutor"
REGION="asia-southeast1"
REPOSITORY="coherence-tutor"

echo "🚀 Deploying Coherence AI Tutor to Google Cloud Run..."

# Set project
gcloud config set project $PROJECT_ID

# Build and push using Artifact Registry
echo "📦 Building and pushing container image to Artifact Registry..."
gcloud builds submit \
  --tag ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest

if [ $? -ne 0 ]; then
  echo "❌ Build failed! Exiting..."
  exit 1
fi

# Deploy to Cloud Run
echo "🌐 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image ${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --timeout 300s \
  --max-instances 10 \
  --min-instances 0 \
  --set-secrets="FLASK_SECRET_KEY=FLASK_SECRET_KEY:latest" \
  --set-secrets="JWT_SECRET=JWT_SECRET:latest" \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --set-secrets="DB_PASSWORD=DB_PASSWORD:latest" \
  --env-vars-file=env.yaml

if [ $? -ne 0 ]; then
  echo "❌ Deployment failed!"
  exit 1
fi

echo "✅ Deployment complete!"
echo "🔗 Service URL:"
gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)"