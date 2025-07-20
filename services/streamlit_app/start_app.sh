#!/bin/bash

# Script to start the Streamlit web application

# Set script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR"

# Create logs directory
mkdir -p logs

# Function to check if port is available
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null ; then
        echo "Port $port is already in use"
        return 1
    else
        echo "Port $port is available"
        return 0
    fi
}

# Function to kill existing Streamlit processes
kill_streamlit() {
    echo "Killing existing Streamlit processes..."
    pkill -f streamlit || true
    sleep 2
}

# Function to start Streamlit
start_streamlit() {
    echo "Starting Streamlit application..."
    
    # Install/update dependencies
    echo "Installing dependencies..."
    pip install -r requirements.txt
    
    # Start Streamlit
    nohup streamlit run app.py \
        --server.port=8501 \
        --server.headless=true \
        --server.enableCORS=false \
        --server.enableXsrfProtection=false \
        --browser.gatherUsageStats=false \
        > streamlit.log 2>&1 &
    
    # Get the PID
    STREAMLIT_PID=$!
    echo "Streamlit started with PID: $STREAMLIT_PID"
    
    # Wait for startup
    echo "Waiting for Streamlit to start..."
    sleep 10
    
    # Check if it's running
    if curl -f http://localhost:8501/healthz >/dev/null 2>&1; then
        echo "✅ Streamlit is running successfully at http://localhost:8501"
        return 0
    else
        echo "❌ Failed to start Streamlit"
        return 1
    fi
}

# Function to check API health
check_api() {
    echo "Checking API health..."
    if curl -f http://localhost:8087/health >/dev/null 2>&1; then
        echo "✅ API is healthy"
        return 0
    else
        echo "⚠️  API is not responding. Make sure the credit scoring API is running."
        return 1
    fi
}

# Main execution
echo "🚀 Starting Credit Scoring Web Application"
echo "========================================="

# Check if port 8501 is available
if ! check_port 8501; then
    echo "Killing existing processes on port 8501..."
    kill_streamlit
fi

# Start Streamlit
if start_streamlit; then
    echo "✅ Streamlit application started successfully!"
    echo ""
    echo "🌐 Access the application at: http://localhost:8501"
    echo "📊 API endpoint: http://localhost:8087"
    echo "📝 Logs available at: $SCRIPT_DIR/streamlit.log"
    echo ""
    
    # Check API health
    check_api
    
    echo ""
    echo "To stop the application, run: pkill -f streamlit"
else
    echo "❌ Failed to start Streamlit application"
    exit 1
fi