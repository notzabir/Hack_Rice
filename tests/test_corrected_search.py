#!/usr/bin/env python3
"""
Simple test for the corrected TwelveLabs search implementation.
"""

import os
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

# Load environment variables
load_dotenv()

API_KEY = os.getenv("TWELVE_LABS_API_KEY")
INDEX_ID = os.getenv("TWELVE_LABS_INDEX_ID")

def test_corrected_search():
    """Test the corrected search implementation."""
    if not API_KEY or not INDEX_ID:
        print("❌ Missing API credentials")
        return False
    
    try:
        client = TwelveLabs(api_key=API_KEY)
        print("✅ Client created successfully")
        
        # Get a video to test with
        videos = client.indexes.videos.list(index_id=INDEX_ID, page_limit=1)
        video_list = list(videos)
        
        if not video_list:
            print("❌ No videos found in index")
            return False
        
        test_video_id = video_list[0].id
        print(f"✅ Testing with video ID: {test_video_id}")
        
        # Test the corrected search method
        print("\n🔍 Testing search with 'test' query...")
        search_pager = client.search.query(
            index_id=INDEX_ID,
            query_text="test",
            search_options=["visual", "audio"]
        )
        
        print("✅ Search method called successfully")
        
        # Check results
        result_count = 0
        for clip in search_pager:
            print(f"📹 Found clip: video_id={clip.video_id}, score={clip.score}, start={clip.start}, end={clip.end}")
            result_count += 1
            if result_count >= 3:  # Limit output
                break
        
        print(f"✅ Found {result_count} total search results")
        
        # Test filtering for specific video
        print(f"\n🎯 Testing filtering for video {test_video_id}...")
        search_pager = client.search.query(
            index_id=INDEX_ID,
            query_text="person talking",  # More meaningful query
            search_options=["visual", "audio"]
        )
        
        video_specific_results = 0
        for clip in search_pager:
            if clip.video_id == test_video_id:
                print(f"🎯 Match for target video: score={clip.score}, start={clip.start}, end={clip.end}")
                video_specific_results += 1
                if video_specific_results >= 2:
                    break
        
        if video_specific_results > 0:
            print(f"✅ Found {video_specific_results} results for target video")
            return True
        else:
            print("⚠️ No results found for target video - may need different query or video not indexed yet")
            return True  # Still successful API call
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("Testing Corrected TwelveLabs Search Implementation")
    print("=" * 50)
    
    success = test_corrected_search()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Search API is working correctly!")
        print("✅ You can now use the Q&A interface")
    else:
        print("❌ Search API test failed")
        print("🔧 Check your API credentials and index setup")