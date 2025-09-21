import os
import requests
from moviepy.editor import VideoFileClip
from twelvelabs import TwelveLabs
from dotenv import load_dotenv
import io
import m3u8
from urllib.parse import urljoin
import yt_dlp
import json
import re

# Load environment variables
load_dotenv()

API_KEY = os.getenv("API_KEY") or os.getenv("TWELVE_LABS_API_KEY")
INDEX_ID = os.getenv("INDEX_ID")

# Validate required environment variables
if not API_KEY:
    raise ValueError(
        "TwelveLabs API key not found. Please set either 'API_KEY' or 'TWELVE_LABS_API_KEY' environment variable. "
        "You can create a .env file in the project root with:\n"
        "API_KEY=your_api_key_here\n"
        "INDEX_ID=your_index_id_here"
    )

if not INDEX_ID:
    raise ValueError(
        "TwelveLabs INDEX_ID not found. Please set 'INDEX_ID' environment variable. "
        "You can create a .env file in the project root with:\n"
        "API_KEY=your_api_key_here\n"
        "INDEX_ID=your_index_id_here"
    )

def seconds_to_mmss(seconds):
    minutes, seconds = divmod(int(seconds), 60)
    return f"{minutes:02d}:{seconds:02d}"

def mmss_to_seconds(mmss):
    minutes, seconds = map(int, mmss.split(':'))
    return minutes * 60 + seconds

def generate_timestamps(client, video_id, start_time=0):
    try:
        gist = client.summarize(video_id=video_id, type="chapter")
        chapter_text = "\n".join([f"{seconds_to_mmss(chapter.start + start_time)}-{chapter.chapter_title}" for chapter in gist.chapters])
        return chapter_text, gist.chapters[-1].start + start_time
    except Exception as e:
        raise Exception(f"An error occurred while generating timestamps: {str(e)}")

# Utitily function to trim the video based on the time stamps
def trim_video(input_path, output_path, start_time, end_time):
    with VideoFileClip(input_path) as video:
        new_video = video.subclip(start_time, end_time)
        new_video.write_videofile(output_path, codec="libx264", audio_codec="aac")

# Based on the speicific Index_ID, fetching all the video_id
def fetch_existing_videos():
    try:
        client = TwelveLabs(api_key=API_KEY)
        videos_pager = client.indexes.videos.list(index_id=INDEX_ID, page=1, page_limit=10, sort_by="created_at", sort_option="desc")
        return [video for video in videos_pager]
    except Exception as e:
        raise Exception(f"Failed to fetch videos: {str(e)}")

# Utility function to retrieve the URL of the video with video_id
def get_video_url(video_id):
    try:
        client = TwelveLabs(api_key=API_KEY)
        video = client.indexes.videos.retrieve(index_id=INDEX_ID, video_id=video_id)
        
        # Check if HLS video URL is available
        if hasattr(video, 'hls') and video.hls and hasattr(video.hls, 'video_url') and video.hls.video_url:
            return video.hls.video_url
        else:
            # Return None if no streaming URL is available (video wasn't uploaded with enable_video_stream=True)
            return None
    except Exception as e:
        raise Exception(f"Failed to get video URL: {str(e)}")


# Utility function to handle and process the video clips larger than 30 mins
def process_video(client, video_path, video_type):
    with VideoFileClip(video_path) as clip:
        duration = clip.duration

    if duration > 3600:
        raise Exception("Video duration exceeds 1 hour. Please upload a shorter video.")

    if video_type == "Basic Video (less than 30 mins)":
        with open(video_path, "rb") as video_file:
            task = client.tasks.create(index_id=INDEX_ID, video_file=video_file, enable_video_stream=True)
        
        task = client.tasks.wait_for_done(task_id=task.id, sleep_interval=5)
        if task.status == "ready":
            timestamps, _ = generate_timestamps(client, task.video_id)
            return timestamps, task.video_id
        else:
            raise Exception(f"Indexing failed with status {task.status}")
    
    elif video_type == "Podcast (30 mins to 1 hour)":
        trimmed_path = os.path.join(os.path.dirname(video_path), "trimmed_1.mp4")
        trim_video(video_path, trimmed_path, 0, 1800)
        
        with open(trimmed_path, "rb") as video_file:
            task1 = client.tasks.create(index_id=INDEX_ID, video_file=video_file, enable_video_stream=True)
        task1 = client.tasks.wait_for_done(task_id=task1.id, sleep_interval=5)
        os.remove(trimmed_path)
        
        if task1.status != "ready":
            raise Exception(f"Indexing failed with status {task1.status}")
        
        timestamps, end_time = generate_timestamps(client, task1.video_id)
        
        if duration > 1800:
            trimmed_path = os.path.join(os.path.dirname(video_path), "trimmed_2.mp4")
            trim_video(video_path, trimmed_path, 1800, int(duration))
            
            with open(trimmed_path, "rb") as video_file:
                task2 = client.tasks.create(index_id=INDEX_ID, video_file=video_file, enable_video_stream=True)
            task2 = client.tasks.wait_for_done(task_id=task2.id, sleep_interval=5)
            os.remove(trimmed_path)
            
            if task2.status != "ready":
                raise Exception(f"Indexing failed with status {task2.status}")
            
            timestamps_2, _ = generate_timestamps(client, task2.video_id, start_time=end_time)
            timestamps += "\n" + timestamps_2
        
        return timestamps, task1.video_id


# Utility function to render the video on the UI
def get_hls_player_html(video_url):
    return f"""
    <script src="https://cdn.jsdelivr.net/npm/hls.js@latest"></script>
    <style>
        #video-container {{
            position: relative;
            width: 100%;
            padding-bottom: 56.25%;
            overflow: hidden;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }}
        #video {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: contain;
        }}
    </style>
    <div id="video-container">
        <video id="video" controls></video>
    </div>
    <script>
        var video = document.getElementById('video');
        var videoSrc = "{video_url}";
        if (Hls.isSupported()) {{
            var hls = new Hls();
            hls.loadSource(videoSrc);
            hls.attachMedia(video);
            hls.on(Hls.Events.MANIFEST_PARSED, function() {{
                video.pause();
            }});
        }}
        else if (video.canPlayType('application/vnd.apple.mpegurl')) {{
            video.src = videoSrc;
            video.addEventListener('loadedmetadata', function() {{
                video.pause();
            }});
        }}
    </script>
    """

# Function to downlaod the video segments after the trimming is done
def download_video_segment(video_id, start_time, end_time=None):
    video_url = get_video_url(video_id)
    if not video_url:
        raise Exception("Failed to get video URL")

    playlist = m3u8.load(video_url)
    
    start_seconds = mmss_to_seconds(start_time)
    end_seconds = mmss_to_seconds(end_time) if end_time else None

    total_duration = 0
    segments_to_download = []
    for segment in playlist.segments:
        if total_duration >= start_seconds and (end_seconds is None or total_duration < end_seconds):
            segments_to_download.append(segment)
        total_duration += segment.duration
        if end_seconds is not None and total_duration >= end_seconds:
            break

    buffer = io.BytesIO()
    for segment in segments_to_download:
        segment_url = urljoin(video_url, segment.uri)
        response = requests.get(segment_url)
        if response.status_code == 200:
            buffer.write(response.content)
        else:
            raise Exception(f"Failed to download segment: {segment_url}")

    buffer.seek(0)
    return buffer.getvalue()

# Utility function to download the indexed video with the url from video_id
def download_video(url, output_filename):
    ydl_opts = {
        'format': 'best',
        'outtmpl': output_filename,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

# Utitily Function to Parse the Segment
def parse_segments(segment_text):
    lines = segment_text.strip().split('\n')
    segments = []
    for i, line in enumerate(lines):
        start, description = line.split('-', 1)
        start_time = mmss_to_seconds(start.strip())
        if i < len(lines) - 1:
            end = lines[i+1].split('-')[0]
            end_time = mmss_to_seconds(end.strip())
        else:
            end_time = None
        segments.append((start_time, end_time, description.strip()))
    return segments


# Utiltiy function to segment the video
def create_video_segments(video_url, segment_info):
    full_video = "full_video.mp4"
    segments = parse_segments(segment_info)

    try:
        # Download the full video clip
        download_video(video_url, full_video)
        
        for i, (start_time, end_time, description) in enumerate(segments):
            output_file = f"{i+1:02d}_{description.replace(' ', '_').lower()}.mp4"
            trim_video(full_video, output_file, start_time, end_time)
            yield output_file, description
        
        os.remove(full_video)
    
    except yt_dlp.utils.DownloadError as e:
        raise Exception(f"An error occurred while downloading: {str(e)}")
    except Exception as e:
        raise Exception(f"An unexpected error occurred: {str(e)}")


# QA Interface Functions

def search_video_content(client, video_id=None, query="", max_results=5):
    """
    Search for relevant content across videos based on a query.
    Uses TwelveLabs built-in search API - no manual embeddings needed.
    
    Args:
        client: TwelveLabs client instance
        video_id: If provided, search only within this video. If None, search across all videos in index
        query: Search query text
        max_results: Maximum number of results to return
    """
    try:
        # TwelveLabs handles embeddings/vector search internally
        # Simple search call based on their documentation
        search_pager = client.search.query(
            index_id=INDEX_ID,
            query_text=query,
            search_options=["visual", "audio"]  # Search across visual and audio content
        )
        
        segments = []
        result_count = 0
        
        # Iterate through search results
        for clip in search_pager:
            # If video_id is specified, filter for that video only
            # If video_id is None, include results from all videos
            if (video_id is None or clip.video_id == video_id) and result_count < max_results:
                segment_info = {
                    'start_time': clip.start,
                    'end_time': clip.end,
                    'confidence': clip.confidence,
                    'score': clip.score,
                    'video_id': clip.video_id,  # Include video_id in results
                    'text': getattr(clip, 'text', ''),  # May not always have text
                    'metadata': getattr(clip, 'metadata', {}),
                    'duration': clip.end - clip.start
                }
                segments.append(segment_info)
                result_count += 1
        
        # Sort by score/confidence (highest first)
        segments.sort(key=lambda x: x.get('score', x.get('confidence', 0)), reverse=True)
        return segments
        
    except Exception as e:
        raise Exception(f"Error searching video content: {str(e)}")


def get_video_info(client, video_id):
    """
    Get video information including title/filename for display purposes.
    """
    try:
        video_info = client.indexes.videos.retrieve(index_id=INDEX_ID, video_id=video_id)
        
        # Extract video name/title
        video_name = "Unknown Video"
        if hasattr(video_info, 'metadata') and video_info.metadata:
            if hasattr(video_info.metadata, 'filename'):
                video_name = video_info.metadata.filename
            elif hasattr(video_info.metadata, 'title'):
                video_name = video_info.metadata.title
        
        return {
            'id': video_id,
            'name': video_name,
            'duration': getattr(video_info, 'duration', 0)
        }
    except Exception as e:
        return {
            'id': video_id,
            'name': f"Video {video_id[:8]}...",
            'duration': 0
        }
        
    except Exception as e:
        raise Exception(f"Error searching video content: {str(e)}")


def create_qa_video_snippet(video_url, start_time, end_time, query, snippet_index=1):
    """
    Create a video snippet based on search results.
    """
    try:
        # Clean query for filename
        clean_query = "".join(c for c in query if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_query = clean_query.replace(' ', '_').lower()[:30]  # Limit length
        
        # Create filename
        start_mm_ss = seconds_to_mmss(start_time)
        end_mm_ss = seconds_to_mmss(end_time)
        output_filename = f"qa_snippet_{snippet_index:02d}_{clean_query}_{start_mm_ss}-{end_mm_ss}.mp4"
        
        # Download and trim video
        temp_video = "temp_qa_video.mp4"
        download_video(video_url, temp_video)
        trim_video(temp_video, output_filename, start_time, end_time)
        
        # Clean up temp file
        if os.path.exists(temp_video):
            os.remove(temp_video)
            
        return output_filename
        
    except Exception as e:
        raise Exception(f"Error creating video snippet: {str(e)}")


def format_qa_results(segments, query, client=None, include_rich_analysis=True):
    """
    Format search results for display in the UI with rich content analysis.
    Now includes summaries, quotations, and detailed segment analysis.
    """
    if not segments:
        return f"No relevant segments found for query: '{query}'"
    
    formatted_results = f"📋 **Enhanced Search Results for: '{query}'**\n\n"
    
    # Group results by video for better organization
    videos_with_results = {}
    for segment in segments:
        video_id = segment['video_id']
        if video_id not in videos_with_results:
            videos_with_results[video_id] = []
        videos_with_results[video_id].append(segment)
    
    result_counter = 1
    for video_id, video_segments in videos_with_results.items():
        # Get video info for display
        if client:
            try:
                video_info = get_video_info(client, video_id)
                video_name = video_info['name']
            except:
                video_name = f"Video {video_id[:8]}..."
        else:
            video_name = f"Video {video_id[:8]}..."
        
        formatted_results += f"🎬 **{video_name}**\n"
        
        for segment in video_segments:
            start_time_str = seconds_to_mmss(segment['start_time'])
            end_time_str = seconds_to_mmss(segment['end_time'])
            duration_str = f"{segment['duration']:.1f}s"
            
            # Use score if available, otherwise use confidence
            confidence_value = segment.get('score', segment.get('confidence', 0))
            confidence_percent = f"{confidence_value * 100:.1f}%"
            
            formatted_results += f"**Result {result_counter}:**\n"
            formatted_results += f"⏰ **Time:** {start_time_str} - {end_time_str} ({duration_str})\n"
            formatted_results += f"🎯 **Relevance Score:** {confidence_percent}\n\n"
            
            # Enhanced content analysis if client is available
            if include_rich_analysis and client:
                try:
                    # Generate contextual analysis for this specific segment
                    snippet_analysis = create_contextual_snippet_analysis(
                        client=client,
                        video_id=video_id,
                        start_time=segment['start_time'],
                        end_time=segment['end_time'],
                        query=query
                    )
                    
                    formatted_results += f"📝 **Detailed Analysis:**\n"
                    formatted_results += f"{snippet_analysis['segment_analysis']}\n\n"
                    
                except Exception as e:
                    # If detailed analysis fails, fall back to basic content
                    if segment.get('text'):
                        text_preview = segment['text'][:300] + "..." if len(segment['text']) > 300 else segment['text']
                        formatted_results += f"💬 **Content Preview:** {text_preview}\n\n"
                    else:
                        formatted_results += f"💬 **Content:** Relevant visual/audio content found\n\n"
            else:
                # Basic content display if no rich analysis
                if segment.get('text'):
                    text_preview = segment['text'][:200] + "..." if len(segment['text']) > 200 else segment['text']
                    formatted_results += f"💬 **Content:** {text_preview}\n\n"
            
            formatted_results += "---\n"
            result_counter += 1
        
        formatted_results += "\n"
    
    return formatted_results


def format_qa_results_with_summary(segments, query, client=None):
    """
    Enhanced format that includes video summary along with search results.
    Provides overall context before showing specific segments.
    """
    if not segments:
        return f"No relevant segments found for query: '{query}'"
    
    formatted_results = f"📋 **Comprehensive Analysis for: '{query}'**\n\n"
    
    # Group results by video for better organization
    videos_with_results = {}
    for segment in segments:
        video_id = segment['video_id']
        if video_id not in videos_with_results:
            videos_with_results[video_id] = []
        videos_with_results[video_id].append(segment)
    
    for video_id, video_segments in videos_with_results.items():
        # Get video info for display
        if client:
            try:
                video_info = get_video_info(client, video_id)
                video_name = video_info['name']
            except:
                video_name = f"Video {video_id[:8]}..."
        else:
            video_name = f"Video {video_id[:8]}..."
        
        formatted_results += f"🎬 **{video_name}**\n\n"
        
        # Add video summary for context
        if client:
            try:
                summary_result = generate_summary(
                    client=client,
                    video_id=video_id,
                    prompt=f"Provide a summary focusing on content related to: {query}"
                )
                formatted_results += f"📖 **Video Summary:**\n{summary_result['summary']}\n\n"
            except Exception as e:
                formatted_results += f"📖 **Video Summary:** Summary not available\n\n"
        
        # Add highlights for additional context
        if client:
            try:
                highlights_result = generate_highlights(
                    client=client,
                    video_id=video_id,
                    prompt=f"Focus on highlights related to: {query}"
                )
                if highlights_result['highlights']:
                    formatted_results += f"✨ **Key Highlights:**\n"
                    for i, highlight in enumerate(highlights_result['highlights'][:3]):  # Limit to top 3
                        time_str = f"{seconds_to_mmss(highlight['start_sec'])} - {seconds_to_mmss(highlight['end_sec'])}"
                        formatted_results += f"{i+1}. **{time_str}:** {highlight['highlight']}\n"
                    formatted_results += "\n"
            except Exception as e:
                pass  # Skip highlights if they fail
        
        # Now show detailed search results
        formatted_results += f"🔍 **Specific Search Results:**\n"
        result_counter = 1
        for segment in video_segments:
            start_time_str = seconds_to_mmss(segment['start_time'])
            end_time_str = seconds_to_mmss(segment['end_time'])
            duration_str = f"{segment['duration']:.1f}s"
            
            confidence_value = segment.get('score', segment.get('confidence', 0))
            confidence_percent = f"{confidence_value * 100:.1f}%"
            
            formatted_results += f"**Result {result_counter}:** {start_time_str} - {end_time_str} ({duration_str}) - {confidence_percent}\n"
            
            # Enhanced content analysis
            if client:
                try:
                    snippet_analysis = create_contextual_snippet_analysis(
                        client=client,
                        video_id=video_id,
                        start_time=segment['start_time'],
                        end_time=segment['end_time'],
                        query=query
                    )
                    formatted_results += f"{snippet_analysis['segment_analysis']}\n\n"
                except Exception as e:
                    if segment.get('text'):
                        text_preview = segment['text'][:200] + "..." if len(segment['text']) > 200 else segment['text']
                        formatted_results += f"Content: {text_preview}\n\n"
            
            result_counter += 1
        
        formatted_results += "---\n\n"
    
    return formatted_results


def get_video_qa_capabilities(client, video_id):
    """
    Check if video is ready for search by checking its indexing status.
    TwelveLabs handles embeddings internally - we just need to check if indexing is complete.
    """
    try:
        # Get video information to check if it's indexed and ready
        video_info = client.indexes.videos.retrieve(index_id=INDEX_ID, video_id=video_id)
        
        # Check if video is fully indexed and ready for search
        is_ready = False
        
        # Check different status indicators
        if hasattr(video_info, 'indexed_at') and video_info.indexed_at:
            is_ready = True
        elif hasattr(video_info, 'ready') and video_info.ready:
            is_ready = True
        elif hasattr(video_info, 'status') and video_info.status == 'ready':
            is_ready = True
        
        return {
            'visual_search': is_ready,
            'conversation_search': is_ready,
            'text_search': is_ready,
            'ready_for_search': is_ready
        }
        
    except Exception as e:
        print(f"Warning: Could not check video status: {str(e)}")
        # If we can't check status, assume it might be ready and let the search try
        return {
            'visual_search': True,
            'conversation_search': True,
            'text_search': True,
            'ready_for_search': True
        }


def test_search_capability(client, video_id):
    """
    Simplified test - just try a basic search to see if it works.
    """
    try:
        # Try a simple search to test if the video is searchable
        search_pager = client.search.query(
            index_id=INDEX_ID,
            query_text="test",
            search_options=["visual", "audio"]
        )
        
        # Check if we get any results for this video
        for clip in search_pager:
            if clip.video_id == video_id:
                return {
                    'visual_search': True,
                    'conversation_search': True,
                    'text_search': True,
                    'ready_for_search': True
                }
        
        # No results found for this video - might not be indexed yet
        return {
            'visual_search': False,
            'conversation_search': False,
            'text_search': False,
            'ready_for_search': False
        }
        
    except Exception as e:
        print(f"Search capability test failed: {str(e)}")
        return {
            'visual_search': False,
            'conversation_search': False,
            'text_search': False,
            'ready_for_search': False
        }


# Enhanced Content Analysis Functions

def generate_summary(client, video_id, prompt=None, temperature=0.3):
    """
    Generate a concise summary of video content using TwelveLabs summarize API.
    
    Args:
        client: TwelveLabs client instance
        video_id: The unique identifier of the video
        prompt: Optional custom prompt to guide the summary generation
        temperature: Controls randomness (0.0-1.0, lower = more deterministic)
    
    Returns:
        Dictionary with summary text and metadata
    """
    try:
        # Use TwelveLabs summarize API with type="summary"
        result = client.summarize(
            video_id=video_id,
            type="summary",
            prompt=prompt,
            temperature=temperature
        )
        
        return {
            'summary': result.summary,
            'id': result.id,
            'usage': getattr(result, 'usage', {}),
            'video_id': video_id
        }
        
    except Exception as e:
        raise Exception(f"Error generating summary: {str(e)}")


def generate_chapters(client, video_id, prompt=None, temperature=0.3):
    """
    Generate chronological chapters with timestamps and headlines.
    
    Args:
        client: TwelveLabs client instance
        video_id: The unique identifier of the video
        prompt: Optional custom prompt to guide the chapter generation
        temperature: Controls randomness (0.0-1.0, lower = more deterministic)
    
    Returns:
        Dictionary with chapters array and metadata
    """
    try:
        # Use TwelveLabs summarize API with type="chapter"
        result = client.summarize(
            video_id=video_id,
            type="chapter",
            prompt=prompt,
            temperature=temperature
        )
        
        chapters_data = []
        for chapter in result.chapters:
            chapters_data.append({
                'chapter_number': chapter.chapter_number,
                'start_sec': chapter.start_sec,
                'end_sec': chapter.end_sec,
                'chapter_title': chapter.chapter_title,
                'chapter_summary': chapter.chapter_summary,
                'duration': chapter.end_sec - chapter.start_sec
            })
        
        return {
            'chapters': chapters_data,
            'id': result.id,
            'usage': getattr(result, 'usage', {}),
            'video_id': video_id
        }
        
    except Exception as e:
        raise Exception(f"Error generating chapters: {str(e)}")


def generate_highlights(client, video_id, prompt=None, temperature=0.3):
    """
    Generate the most significant events/highlights with timestamps.
    
    Args:
        client: TwelveLabs client instance
        video_id: The unique identifier of the video
        prompt: Optional custom prompt to guide the highlights generation
        temperature: Controls randomness (0.0-1.0, lower = more deterministic)
    
    Returns:
        Dictionary with highlights array and metadata
    """
    try:
        # Use TwelveLabs summarize API with type="highlight"
        result = client.summarize(
            video_id=video_id,
            type="highlight",
            prompt=prompt,
            temperature=temperature
        )
        
        highlights_data = []
        for highlight in result.highlights:
            highlights_data.append({
                'highlight': highlight.highlight,
                'start_sec': highlight.start_sec,
                'end_sec': highlight.end_sec,
                'duration': highlight.end_sec - highlight.start_sec
            })
        
        return {
            'highlights': highlights_data,
            'id': result.id,
            'usage': getattr(result, 'usage', {}),
            'video_id': video_id
        }
        
    except Exception as e:
        raise Exception(f"Error generating highlights: {str(e)}")


def generate_open_analysis(client, video_id, prompt, temperature=0.3, streaming=False):
    """
    Perform open-ended analysis with custom prompts for detailed content analysis.
    
    Args:
        client: TwelveLabs client instance
        video_id: The unique identifier of the video
        prompt: Custom prompt to guide the analysis (required, max 2000 tokens)
        temperature: Controls randomness (0.0-1.0, lower = more deterministic)
        streaming: Whether to use streaming responses (True) or non-streaming (False)
    
    Returns:
        Dictionary with analysis text and metadata
    """
    try:
        if streaming:
            # Use streaming response for real-time text generation
            text_stream = client.analyze_stream(
                video_id=video_id,
                prompt=prompt,
                temperature=temperature
            )
            
            # Collect streaming text
            analysis_text = ""
            for text in text_stream:
                if text.event_type == "text_generation":
                    analysis_text += text.text
            
            return {
                'analysis': analysis_text,
                'streaming': True,
                'video_id': video_id
            }
        else:
            # Use non-streaming response for complete text at once
            result = client.analyze(
                video_id=video_id,
                prompt=prompt,
                temperature=temperature
            )
            
            # According to TwelveLabs documentation, NonStreamAnalyzeResponse has 'data' attribute
            analysis_text = getattr(result, 'data', '')
            
            return {
                'analysis': analysis_text,
                'id': getattr(result, 'id', 'unknown'),
                'usage': getattr(result, 'usage', {}),
                'streaming': False,
                'video_id': video_id
            }
        
    except Exception as e:
        raise Exception(f"Error performing open-ended analysis: {str(e)}")


# ---- Advanced Feature Helpers: Topics, Entities, and Follow-up Q&A ----

def _extract_json_from_text(text):
    """
    Best-effort JSON extraction from model output. Returns Python object or None.
    """
    if not text:
        return None
    # Try direct JSON first
    try:
        return json.loads(text)
    except Exception:
        pass
    # Fallback: find first {...} block
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    # Fallback: find [...] array
    match = re.search(r"\[[\s\S]*\]", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def generate_topics(client, video_id, max_topics=10, temperature=0.2):
    """
    Extract key topics from a video using TwelveLabs analyze API with a structured prompt.
    Returns a dict with a list of topics and metadata.
    """
    prompt = f"""
    You are extracting concise key TOPICS from a video. Analyze the entire content and output STRICT JSON.
    JSON schema:
    {{
      "topics": [
        {{
          "name": "string",            // short title of topic
          "salience": 0.0,              // 0-1 relevance score
          "occurrences": 0,             // number of mentions/scenes
          "first_sec": 0,               // first second where topic appears
          "last_sec": 0,                // last second where topic appears
          "keywords": ["string"]       // a few related keywords
        }}
      ]
    }}
    Rules:
    - Return ONLY JSON. No prose.
    - Limit to {max_topics} top topics.
    """
    result = generate_open_analysis(client, video_id, prompt, temperature=temperature, streaming=False)
    data = _extract_json_from_text(result.get('analysis')) or {"topics": []}
    # Normalize types
    topics = []
    for t in data.get("topics", []):
        topics.append({
            "name": t.get("name") or "Unknown",
            "salience": float(t.get("salience", 0.0)),
            "occurrences": int(t.get("occurrences", 0)),
            "first_sec": float(t.get("first_sec", 0)),
            "last_sec": float(t.get("last_sec", 0)),
            "keywords": t.get("keywords", [])[:5],
        })
    topics.sort(key=lambda x: x["salience"], reverse=True)
    return {"topics": topics, "video_id": video_id}


def generate_entities(client, video_id, temperature=0.2):
    """
    Extract named entities (people, organizations, places, products) from a video.
    Returns a dict with categorized entities.
    """
    prompt = """
    Extract NAMED ENTITIES from the video and output STRICT JSON only.
    Categories: person, organization, place, product, other.
    JSON schema:
    {
      "entities": [
        {
          "name": "string",
          "type": "person|organization|place|product|other",
          "mentions": 0,
          "confidence": 0.0,
          "first_sec": 0,
          "last_sec": 0
        }
      ]
    }
    Rules: Return ONLY JSON, no extra text.
    """
    result = generate_open_analysis(client, video_id, prompt, temperature=temperature, streaming=False)
    data = _extract_json_from_text(result.get('analysis')) or {"entities": []}
    entities = []
    for e in data.get("entities", []):
        ent_type = (e.get("type") or "other").lower()
        if ent_type not in {"person", "organization", "place", "product", "other"}:
            ent_type = "other"
        entities.append({
            "name": e.get("name") or "Unknown",
            "type": ent_type,
            "mentions": int(e.get("mentions", 0)),
            "confidence": float(e.get("confidence", 0.0)),
            "first_sec": float(e.get("first_sec", 0)),
            "last_sec": float(e.get("last_sec", 0)),
        })
    # Sort by confidence then mentions
    entities.sort(key=lambda x: (x["confidence"], x["mentions"]), reverse=True)
    return {"entities": entities, "video_id": video_id}


def rewrite_followup_query(client, video_id, chat_history, followup_text, temperature=0.2):
    """
    Rewrites a follow-up question into a standalone query using conversation context.
    chat_history: list of {"role": "user|assistant", "content": "..."}
    Returns a dict {"query": "..."}
    """
    # If no video_id context is available, return the follow-up as-is
    if not video_id:
        return {"query": followup_text}

    # Build a compact conversation context (last 6 turns max)
    history_tail = chat_history[-6:] if chat_history else []
    convo = "\n".join([f"{m['role']}: {m['content']}" for m in history_tail])
    prompt = f"""
    You're a helpful assistant that converts a follow-up question into a standalone query.
    Conversation so far:\n{convo}\n
    Follow-up: {followup_text}

    Output STRICT JSON: {{"query": "<standalone rewritten query>"}}
    Only return JSON. No extra text.
    """
    result = generate_open_analysis(client, video_id, prompt, temperature=temperature, streaming=False)
    data = _extract_json_from_text(result.get('analysis')) or {}
    query = data.get("query") or followup_text
    return {"query": query}


def create_contextual_snippet_analysis(client, video_id, start_time, end_time, query):
    """
    Create a detailed analysis of a specific video segment based on the search query.
    Combines multiple analysis types for rich content.
    
    Args:
        client: TwelveLabs client instance
        video_id: The unique identifier of the video
        start_time: Start time in seconds
        end_time: End time in seconds
        query: Original search query for context
    
    Returns:
        Dictionary with comprehensive analysis of the segment
    """
    try:
        # Create a contextual prompt for the specific segment
        duration = end_time - start_time
        start_time_str = seconds_to_mmss(start_time)
        end_time_str = seconds_to_mmss(end_time)
        
        analysis_prompt = f"""
        Analyze the video segment from {start_time_str} to {end_time_str} (duration: {duration:.1f} seconds) 
        in the context of the search query: "{query}".
        
        Provide:
        1. A detailed summary of what happens in this specific segment
        2. Key quotations or important spoken content (if any)
        3. Visual elements and their relevance to the search query
        4. How this segment answers or relates to the search query
        5. Any significant actions, objects, or concepts visible or discussed
        
        Be specific and detailed about the content within this time range.
        """
        
        # Use open-ended analysis for this specific context
        analysis_result = generate_open_analysis(
            client=client,
            video_id=video_id,
            prompt=analysis_prompt,
            temperature=0.2,  # Lower temperature for more precise analysis
            streaming=False
        )
        
        return {
            'segment_analysis': analysis_result['analysis'],
            'start_time': start_time,
            'end_time': end_time,
            'duration': duration,
            'query_context': query,
            'video_id': video_id
        }
        
    except Exception as e:
        # If detailed analysis fails, return basic information
        return {
            'segment_analysis': f"Analysis not available for this segment ({seconds_to_mmss(start_time)} - {seconds_to_mmss(end_time)})",
            'start_time': start_time,
            'end_time': end_time,
            'duration': end_time - start_time,
            'query_context': query,
            'video_id': video_id
        }


def create_analysis_video_snippet(video_url, start_time, end_time, title, snippet_type="analysis"):
    """
    Create a video snippet for analysis results (chapters, highlights, etc.).
    Now handles HLS streaming URLs from TwelveLabs.
    
    Args:
        video_url: URL of the source video (can be HLS or regular URL)
        start_time: Start time in seconds (can be float)
        end_time: End time in seconds (can be float)
        title: Title/description for the snippet
        snippet_type: Type of snippet (chapter, highlight, analysis)
    
    Returns:
        Filename of the created snippet
    """
    try:
        # Clean title for filename
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_title = clean_title.replace(' ', '_').lower()[:40]  # Limit length
        
        # Create filename with timestamp (replace colons with underscores for Windows compatibility)
        start_mm_ss = seconds_to_mmss(start_time).replace(':', '_')
        end_mm_ss = seconds_to_mmss(end_time).replace(':', '_')
        duration = end_time - start_time
        
        output_filename = f"{snippet_type}_{clean_title}_{start_mm_ss}-{end_mm_ss}_{duration:.1f}s.mp4"
        
        # Check if this is an HLS URL (from TwelveLabs streaming)
        if video_url and '.m3u8' in video_url:
            # Handle HLS streaming URL - use ffmpeg directly for HLS streams
            try:
                # Use ffmpeg to extract segment from HLS stream with proper encoding
                import subprocess
                cmd = [
                    'ffmpeg', 
                    '-i', video_url,
                    '-ss', str(start_time),
                    '-t', str(duration),
                    '-c:v', 'libx264',  # Re-encode video to ensure compatibility
                    '-c:a', 'aac',      # Re-encode audio to ensure compatibility
                    '-avoid_negative_ts', 'make_zero',
                    '-movflags', '+faststart',  # Optimize for web playback
                    output_filename,
                    '-y'  # Overwrite output file
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    raise Exception(f"FFmpeg failed: {result.stderr}")
                
                # Verify the file was created and has content
                if not os.path.exists(output_filename):
                    raise Exception("Output file was not created")
                
                file_size = os.path.getsize(output_filename)
                if file_size < 1000:  # Less than 1KB indicates a problem
                    raise Exception(f"Output file is too small ({file_size} bytes), likely corrupted")
                        
            except Exception as e:
                raise Exception(f"Could not create snippet from HLS stream: {str(e)}")
        else:
            # Handle regular video URLs (YouTube, etc.)
            temp_video = f"temp_{snippet_type}_video.mp4"
            download_video(video_url, temp_video)
            trim_video(temp_video, output_filename, start_time, end_time)
            
            # Clean up temp file
            if os.path.exists(temp_video):
                os.remove(temp_video)
            
        return output_filename
        
    except Exception as e:
        raise Exception(f"Error creating {snippet_type} snippet: {str(e)}")


def create_hls_snippet_alternative(video_id, start_time, end_time, title, snippet_type="analysis"):
    """
    Alternative method to create snippets from indexed TwelveLabs videos.
    Uses ffmpeg to properly handle HLS streams and create valid MP4 files.
    """
    try:
        # Get the HLS video URL for the indexed video
        video_url = get_video_url(video_id)
        if not video_url:
            raise Exception("Failed to get video URL for indexed video")
        
        # Clean title for filename (remove any problematic characters)
        clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_title = clean_title.replace(' ', '_').lower()[:40]
        
        # Create filename with timestamp (replace colons with underscores for Windows compatibility)
        start_mm_ss = seconds_to_mmss(start_time).replace(':', '_')
        end_mm_ss = seconds_to_mmss(end_time).replace(':', '_')
        duration = end_time - start_time
        
        output_filename = f"{snippet_type}_{clean_title}_{start_mm_ss}-{end_mm_ss}_{duration:.1f}s.mp4"
        
        # Use ffmpeg to extract segment from HLS stream
        import subprocess
        cmd = [
            'ffmpeg', 
            '-i', video_url,
            '-ss', str(start_time),
            '-t', str(duration),
            '-c:v', 'libx264',  # Re-encode video to ensure compatibility
            '-c:a', 'aac',      # Re-encode audio to ensure compatibility
            '-avoid_negative_ts', 'make_zero',
            '-movflags', '+faststart',  # Optimize for web playback
            output_filename,
            '-y'  # Overwrite output file
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"FFmpeg failed: {result.stderr}")
        
        # Verify the file was created and has content
        if not os.path.exists(output_filename):
            raise Exception("Output file was not created")
        
        file_size = os.path.getsize(output_filename)
        if file_size < 1000:  # Less than 1KB indicates a problem
            raise Exception(f"Output file is too small ({file_size} bytes), likely corrupted")
        
        return output_filename
        
    except Exception as e:
        raise Exception(f"Error creating HLS snippet: {str(e)}")


def batch_create_chapter_snippets(video_url, chapters_result):
    """
    Create video snippets for all chapters in a chapters result.
    
    Args:
        video_url: URL of the source video
        chapters_result: Result from generate_chapters()
    
    Returns:
        List of created snippet filenames with metadata
    """
    created_snippets = []
    
    try:
        for chapter in chapters_result['chapters']:
            try:
                snippet_filename = create_analysis_video_snippet(
                    video_url=video_url,
                    start_time=chapter['start_sec'],
                    end_time=chapter['end_sec'],
                    title=chapter['chapter_title'],
                    snippet_type="chapter"
                )
                
                created_snippets.append({
                    'filename': snippet_filename,
                    'title': chapter['chapter_title'],
                    'summary': chapter['chapter_summary'],
                    'start_time': chapter['start_sec'],
                    'end_time': chapter['end_sec'],
                    'chapter_number': chapter['chapter_number']
                })
                
            except Exception as e:
                print(f"Error creating snippet for chapter {chapter['chapter_number']}: {str(e)}")
                continue
                
    except Exception as e:
        raise Exception(f"Error in batch chapter snippet creation: {str(e)}")
    
    return created_snippets


def batch_create_highlight_snippets(video_url, highlights_result):
    """
    Create video snippets for all highlights in a highlights result.
    
    Args:
        video_url: URL of the source video
        highlights_result: Result from generate_highlights()
    
    Returns:
        List of created snippet filenames with metadata
    """
    created_snippets = []
    
    try:
        for i, highlight in enumerate(highlights_result['highlights'], 1):
            try:
                snippet_filename = create_analysis_video_snippet(
                    video_url=video_url,
                    start_time=highlight['start_sec'],
                    end_time=highlight['end_sec'],
                    title=highlight['highlight'],
                    snippet_type="highlight"
                )
                
                created_snippets.append({
                    'filename': snippet_filename,
                    'title': highlight['highlight'],
                    'summary': highlight.get('highlight_summary', ''),
                    'start_time': highlight['start_sec'],
                    'end_time': highlight['end_sec'],
                    'highlight_number': i
                })
                
            except Exception as e:
                print(f"Error creating snippet for highlight {i}: {str(e)}")
                continue
                
    except Exception as e:
        raise Exception(f"Error in batch highlight snippet creation: {str(e)}")
    
    return created_snippets