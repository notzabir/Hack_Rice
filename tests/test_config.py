#!/usr/bin/env python3
"""
Test script to verify TwelveLabs configuration and API connectivity.
Run this before using the main application to ensure everything is set up correctly.
"""

import os
from dotenv import load_dotenv
from twelvelabs import TwelveLabs

def test_configuration():
    """Test if the configuration is properly set up."""
    print("🔧 Testing TwelveLabs Configuration...")
    
    # Load environment variables
    load_dotenv()
    
    # Check for required environment variables
    api_key = os.getenv("TWELVE_LABS_API_KEY")
    index_id = os.getenv("TWELVE_LABS_INDEX_ID")
    
    if not api_key:
        print("❌ TWELVE_LABS_API_KEY not found in environment variables")
        print("   Please add your API key to the .env file")
        return False
    
    if not index_id:
        print("❌ TWELVE_LABS_INDEX_ID not found in environment variables")
        print("   Please add your index ID to the .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:8]}...")
    print(f"✅ Index ID found: {index_id}")
    
    # Test API connection
    try:
        print("\n🌐 Testing API connection...")
        client = TwelveLabs(api_key=api_key)
        
        # Try to get index information
        index = client.indexes.retrieve(index_id)
        print(f"✅ Successfully connected to index: {index.name}")
        print(f"   Engine: {index.engine_name}")
        
        # Test listing videos (if any)
        print("\n📹 Testing video listing...")
        videos = client.indexes.videos.list(index_id=index_id, page_limit=5)
        video_count = len(list(videos))
        print(f"✅ Found {video_count} videos in the index")
        
        if video_count > 0:
            print("   Recent videos:")
            videos = client.indexes.videos.list(index_id=index_id, page_limit=3)
            for video in videos:
                print(f"   - {video.metadata.filename if video.metadata else 'Unknown'} (ID: {video.id})")
        
        return True
        
    except Exception as e:
        print(f"❌ API connection failed: {str(e)}")
        print("   Please check your API key and index ID")
        return False

def main():
    """Main test function."""
    print("TwelveLabs Configuration Test")
    print("=" * 40)
    
    success = test_configuration()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 Configuration test passed! You can now run the main application.")
        print("   Run: streamlit run app.py")
    else:
        print("💥 Configuration test failed. Please check the error messages above.")
        print("   Make sure you have:")
        print("   1. Created a .env file with your API credentials")
        print("   2. Set TWELVE_LABS_API_KEY and TWELVE_LABS_INDEX_ID")
        print("   3. Verified your API key and index ID are correct")

if __name__ == "__main__":
    main()