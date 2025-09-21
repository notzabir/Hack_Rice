#!/usr/bin/env python3
"""
Test script for enhanced TwelveLabs video analysis functionality.
This script tests the new analysis functions to ensure they work correctly.
"""

import os
import sys
from dotenv import load_dotenv

# Add current directory to path to import utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

load_dotenv()

def test_analysis_functions():
    """Test the new analysis functions with basic functionality."""
    
    try:
        from twelvelabs import TwelveLabs
        from utils import (
            API_KEY, INDEX_ID, generate_summary, generate_chapters, 
            generate_highlights, generate_open_analysis, 
            create_contextual_snippet_analysis, fetch_existing_videos
        )
        
        print("✅ Successfully imported all required functions")
        
        # Initialize client
        client = TwelveLabs(api_key=API_KEY)
        print("✅ TwelveLabs client initialized successfully")
        
        # Test fetching existing videos
        try:
            videos = fetch_existing_videos()
            if videos:
                test_video_id = videos[0].id
                print(f"✅ Found {len(videos)} videos in index")
                print(f"📹 Testing with video ID: {test_video_id[:8]}...")
                
                # Test summary generation
                try:
                    print("🔄 Testing summary generation...")
                    summary_result = generate_summary(client, test_video_id)
                    print("✅ Summary generation works!")
                    print(f"   Summary length: {len(summary_result['summary'])} characters")
                except Exception as e:
                    print(f"❌ Summary generation failed: {str(e)}")
                
                # Test chapters generation
                try:
                    print("🔄 Testing chapters generation...")
                    chapters_result = generate_chapters(client, test_video_id)
                    print("✅ Chapters generation works!")
                    print(f"   Number of chapters: {len(chapters_result['chapters'])}")
                except Exception as e:
                    print(f"❌ Chapters generation failed: {str(e)}")
                
                # Test highlights generation
                try:
                    print("🔄 Testing highlights generation...")
                    highlights_result = generate_highlights(client, test_video_id)
                    print("✅ Highlights generation works!")
                    print(f"   Number of highlights: {len(highlights_result['highlights'])}")
                except Exception as e:
                    print(f"❌ Highlights generation failed: {str(e)}")
                
                # Test open-ended analysis
                try:
                    print("🔄 Testing open-ended analysis...")
                    analysis_result = generate_open_analysis(
                        client, 
                        test_video_id, 
                        "Provide a brief overview of the main topics in this video.", 
                        temperature=0.3
                    )
                    print("✅ Open-ended analysis works!")
                    print(f"   Analysis length: {len(analysis_result['analysis'])} characters")
                except Exception as e:
                    print(f"❌ Open-ended analysis failed: {str(e)}")
                
                print("\n🎉 Enhanced video analysis testing completed!")
                
            else:
                print("⚠️  No videos found in index. Please upload a video first.")
                
        except Exception as e:
            print(f"❌ Error fetching videos: {str(e)}")
            
    except ImportError as e:
        print(f"❌ Import error: {str(e)}")
        print("Make sure all dependencies are installed and environment variables are set.")
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")

if __name__ == "__main__":
    print("🚀 Testing Enhanced TwelveLabs Video Analysis Functions")
    print("=" * 60)
    test_analysis_functions()