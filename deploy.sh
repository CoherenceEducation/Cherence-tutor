#!/bin/bash

# Configuration
PROJECT_ID="model-sphere-474807-r6"
SERVICE_NAME="coherence-tutor"
REGION="asia-southeast1"
SECRET_NAME="Coherence-secret-env"

echo "🚀 Deploying Coherence AI Tutor to Google Cloud Run..."

# Set project
gcloud config set project $PROJECT_ID

# Build container image
echo "📦 Building container image..."
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# Deploy to Cloud Run
echo "🌐 Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --timeout 60s \
  --max-instances 10 \
  --min-instances 0 \
  --set-secrets="FLASK_SECRET_KEY=FLASK_SECRET_KEY:latest" \
  --set-secrets="JWT_SECRET=JWT_SECRET:latest" \
  --set-secrets="GEMINI_API_KEY=GEMINI_API_KEY:latest" \
  --set-secrets="DB_PASSWORD=DB_PASSWORD:latest" \
  --set-env-vars="DB_HOST=34.143.232.17" \
  --set-env-vars="DB_PORT=3306" \
  --set-env-vars="DB_USER=root" \
  --set-env-vars="DB_NAME=coherence_tutor" \
  --set-env-vars="FLASK_ENV=production" \
  --set-env-vars="MAX_REQUESTS_PER_MINUTE=5" \
  --set-env-vars="ADMIN_EMAILS=andrew@coherence.org,mina@coherenceeducation.org,support@coherenceeducation.org,evan.senour@gmail.com,gavinli.automation@gmail.com"

echo "✅ Deployment complete!"
echo "🔗 Service URL:"
gcloud run services describe $SERVICE_NAME --region=$REGION --format="value(status.url)"
