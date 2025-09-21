#!/usr/bin/env python3
"""
Test script to figure out the correct TwelveLabs search API parameters.
"""

import os
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

# Load environment variables
load_dotenv()

API_KEY = os.getenv("TWELVE_LABS_API_KEY")
INDEX_ID = os.getenv("TWELVE_LABS_INDEX_ID")

def test_search_api():
    """Test different search API parameter combinations."""
    if not API_KEY or not INDEX_ID:
        print("Missing API credentials")
        return
    
    client = TwelveLabs(api_key=API_KEY)
    
    # Get a video to test with
    try:
        videos = client.indexes.videos.list(index_id=INDEX_ID, page_limit=1)
        video_list = list(videos)
        if not video_list:
            print("No videos found in index")
            return
        
        test_video_id = video_list[0].id
        print(f"Testing with video ID: {test_video_id}")
        
        # Test query 1: Basic parameters
        try:
            print("\n--- Test 1: Basic query ---")
            result = client.search.query(
                query="introduction",
                index_id=INDEX_ID
            )
            print("✅ Test 1 passed - basic query works")
            print(f"Results count: {len(list(result.data))}")
        except Exception as e:
            print(f"❌ Test 1 failed: {e}")
        
        # Test query 2: With search options
        try:
            print("\n--- Test 2: With search options ---")
            result = client.search.query(
                query="introduction",
                index_id=INDEX_ID,
                search_options=["visual", "conversation"]
            )
            print("✅ Test 2 passed - with search options")
        except Exception as e:
            print(f"❌ Test 2 failed: {e}")
        
        # Test query 3: Alternative parameter names
        try:
            print("\n--- Test 3: Alternative parameters ---")
            result = client.search.query(
                query_text="introduction",
                index_id=INDEX_ID
            )
            print("✅ Test 3 passed - query_text parameter")
        except Exception as e:
            print(f"❌ Test 3 failed: {e}")
        
        # Test query 4: With filters
        try:
            print("\n--- Test 4: With video filter ---")
            result = client.search.query(
                query="introduction",
                index_id=INDEX_ID,
                filter={
                    "id": test_video_id
                }
            )
            print("✅ Test 4 passed - with video filter")
        except Exception as e:
            print(f"❌ Test 4 failed: {e}")
        
        # Print API info
        print("\n--- Client inspection ---")
        print("Search client methods:")
        search_methods = [method for method in dir(client.search) if not method.startswith('_')]
        for method in search_methods:
            print(f"  - {method}")
        
    except Exception as e:
        print(f"Error getting test video: {e}")

if __name__ == "__main__":
    test_search_api()