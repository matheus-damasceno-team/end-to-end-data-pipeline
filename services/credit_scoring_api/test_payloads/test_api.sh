#!/bin/bash

# Test script for Credit Scoring API
# Usage: ./test_api.sh [payload_file]
# Example: ./test_api.sh approve_case.json

set -e

# Configuration
API_URL="http://localhost:8087"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD_DIR="$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_color() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to print separator
print_separator() {
    echo "=================================================="
}

# Function to check if API is running
check_api_health() {
    print_color $BLUE "Checking API health..."
    
    if curl -s -f "$API_URL/health" > /dev/null 2>&1; then
        print_color $GREEN "✅ API is running and healthy"
        return 0
    else
        print_color $RED "❌ API is not responding. Please check if the service is running on $API_URL"
        return 1
    fi
}

# Function to test a single payload
test_payload() {
    local payload_file=$1
    local full_path="$PAYLOAD_DIR/$payload_file"
    
    if [ ! -f "$full_path" ]; then
        print_color $RED "❌ File not found: $full_path"
        return 1
    fi
    
    print_separator
    print_color $YELLOW "Testing payload: $payload_file"
    print_separator
    
    # Extract proponente_id from the JSON for better identification
    local proponente_id=$(grep -o '"proponente_id"[[:space:]]*:[[:space:]]*"[^"]*"' "$full_path" | cut -d'"' -f4)
    print_color $BLUE "Proponente ID: $proponente_id"
    
    echo "Request payload:"
    cat "$full_path" | jq '.' 2>/dev/null || cat "$full_path"
    echo ""
    
    print_color $BLUE "Sending request to $API_URL/score..."
    
    # Make the request and capture response
    local response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        -d @"$full_path" \
        "$API_URL/score" 2>/dev/null)
    
    # Extract HTTP status and body
    local http_status=$(echo "$response" | tail -n1 | cut -d: -f2)
    local response_body=$(echo "$response" | head -n -1)
    
    echo "Response (HTTP $http_status):"
    
    if [ "$http_status" = "200" ]; then
        print_color $GREEN "✅ Success!"
        echo "$response_body" | jq '.' 2>/dev/null || echo "$response_body"
        
        # Extract decision for summary
        local decision=$(echo "$response_body" | jq -r '.decision' 2>/dev/null || echo "N/A")
        local score=$(echo "$response_body" | jq -r '.score' 2>/dev/null || echo "N/A")
        
        print_color $GREEN "Decision: $decision | Score: $score"
    else
        print_color $RED "❌ Failed with HTTP $http_status"
        echo "$response_body" | jq '.' 2>/dev/null || echo "$response_body"
    fi
    
    echo ""
}

# Function to test all payloads
test_all_payloads() {
    local payload_files=("approve_case.json" "manual_review_case.json" "deny_case.json")
    
    print_color $YELLOW "Testing all payload files..."
    
    for file in "${payload_files[@]}"; do
        test_payload "$file"
        sleep 1  # Small delay between requests
    done
}

# Function to get model info
get_model_info() {
    print_separator
    print_color $YELLOW "Getting model information..."
    print_separator
    
    local response=$(curl -s -w "\nHTTP_STATUS:%{http_code}" \
        -X GET \
        "$API_URL/model-info" 2>/dev/null)
    
    local http_status=$(echo "$response" | tail -n1 | cut -d: -f2)
    local response_body=$(echo "$response" | head -n -1)
    
    if [ "$http_status" = "200" ]; then
        print_color $GREEN "✅ Model info retrieved successfully!"
        echo "$response_body" | jq '.' 2>/dev/null || echo "$response_body"
    else
        print_color $RED "❌ Failed to get model info (HTTP $http_status)"
        echo "$response_body"
    fi
    
    echo ""
}

# Function to show usage
show_usage() {
    cat << EOF
Credit Scoring API Test Script

Usage:
    $0                          # Test all payload files
    $0 <payload_file>          # Test specific payload file
    $0 --help                  # Show this help message
    $0 --model-info            # Get model information only
    $0 --health                # Check API health only

Available payload files:
    - approve_case.json        # High-income, experienced farmer (expected: APPROVE)
    - manual_review_case.json  # Medium-risk profile (expected: MANUAL_REVIEW)
    - deny_case.json          # High-risk profile (expected: DENY)

Examples:
    $0                         # Test all cases
    $0 approve_case.json      # Test only approval case
    $0 --model-info           # Get current model information

Prerequisites:
    - API must be running on $API_URL
    - curl must be installed
    - jq is recommended for JSON formatting (optional)

EOF
}

# Main script logic
main() {
    # Check if jq is available
    if ! command -v jq &> /dev/null; then
        print_color $YELLOW "⚠️  jq not found. JSON output will not be formatted."
        echo ""
    fi
    
    case "${1:-}" in
        "--help" | "-h")
            show_usage
            exit 0
            ;;
        "--health")
            check_api_health
            exit $?
            ;;
        "--model-info")
            check_api_health || exit 1
            get_model_info
            exit 0
            ;;
        "")
            # No arguments - test all
            check_api_health || exit 1
            test_all_payloads
            get_model_info
            ;;
        *)
            # Specific file provided
            check_api_health || exit 1
            test_payload "$1"
            ;;
    esac
}

# Run main function with all arguments
main "$@"