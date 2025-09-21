import os
import requests
from moviepy.editor import VideoFileClip
from twelvelabs import TwelveLabs
from dotenv import load_dotenv
import io
import m3u8
from urllib.parse import urljoin
import yt_dlp

# Load environment variables
load_dotenv()

API_KEY = os.getenv("API_KEY") or os.getenv("TWELVE_LABS_API_KEY")
INDEX_ID = os.getenv("INDEX_ID")

# Discord configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = os.getenv("DISCORD_CHANNEL_ID")
DISCORD_BOT_ENDPOINT = os.getenv("DISCORD_BOT_ENDPOINT", "http://localhost:8000")

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


def generate_flashcards(client, video_id, num_cards=10, difficulty="medium"):
    """
    Generate educational flashcards from video content using TwelveLabs analysis.
    
    Args:
        client: TwelveLabs client instance
        video_id: The unique identifier of the video
        num_cards: Number of flashcards to generate (default: 10)
        difficulty: Difficulty level - "easy", "medium", "hard" (default: "medium")
    
    Returns:
        Dictionary with flashcards and metadata
    """
    try:
        # Create specialized prompt for flashcard generation
        prompt = f"""Generate {num_cards} educational flashcards from this video content at {difficulty} difficulty level.

Format your response as a JSON structure with the following format:
{{
    "flashcards": [
        {{
            "id": 1,
            "question": "Clear, concise question about key concept",
            "answer": "Detailed answer with explanation",
            "topic": "Main topic/subject area",
            "difficulty": "{difficulty}",
            "timestamp": "MM:SS (if relevant to specific moment)"
        }}
    ],
    "summary": "Brief overview of topics covered in flashcards"
}}

Guidelines for flashcard creation:
- Focus on key concepts, definitions, and important facts
- Make questions clear and specific
- Provide detailed answers with context
- Include timestamp if question relates to specific video moment
- Cover diverse aspects of the video content
- Ensure questions test understanding, not just memorization

Topics to prioritize:
- Main concepts and definitions
- Key processes or procedures shown
- Important names, dates, or facts
- Cause and effect relationships
- Critical thinking applications"""

        # Use TwelveLabs analyze function
        result = client.analyze(
            video_id=video_id,
            prompt=prompt,
            temperature=0.3  # Lower temperature for more consistent educational content
        )
        
        # Extract analysis text
        analysis_text = getattr(result, 'data', '')
        
        # Try to parse JSON from the response
        import json
        try:
            # Look for JSON in the response
            json_start = analysis_text.find('{')
            json_end = analysis_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = analysis_text[json_start:json_end]
                flashcards_data = json.loads(json_str)
            else:
                # Fallback: create structured data from text
                flashcards_data = {
                    "flashcards": [],
                    "summary": "Flashcards generated from video analysis"
                }
                
                # Simple parsing fallback (you can enhance this)
                lines = analysis_text.split('\n')
                current_card = {}
                card_id = 1
                
                for line in lines:
                    line = line.strip()
                    if line.startswith('Q:') or line.startswith('Question:'):
                        if current_card.get('question'):
                            flashcards_data["flashcards"].append(current_card)
                            card_id += 1
                        current_card = {
                            "id": card_id,
                            "question": line.replace('Q:', '').replace('Question:', '').strip(),
                            "difficulty": difficulty,
                            "topic": "Video Content"
                        }
                    elif line.startswith('A:') or line.startswith('Answer:'):
                        if current_card.get('question'):
                            current_card["answer"] = line.replace('A:', '').replace('Answer:', '').strip()
                
                if current_card.get('question') and current_card.get('answer'):
                    flashcards_data["flashcards"].append(current_card)
                    
        except json.JSONDecodeError:
            # If JSON parsing fails, create a simple structure
            flashcards_data = {
                "flashcards": [{
                    "id": 1,
                    "question": "What are the main topics covered in this video?",
                    "answer": analysis_text[:500] + "..." if len(analysis_text) > 500 else analysis_text,
                    "topic": "Video Overview",
                    "difficulty": difficulty
                }],
                "summary": "Generated flashcards from video content analysis"
            }
        
        return {
            'flashcards': flashcards_data.get('flashcards', []),
            'summary': flashcards_data.get('summary', ''),
            'total_cards': len(flashcards_data.get('flashcards', [])),
            'difficulty': difficulty,
            'video_id': video_id,
            'id': getattr(result, 'id', 'unknown'),
            'usage': getattr(result, 'usage', {})
        }
        
    except Exception as e:
        raise Exception(f"Error generating flashcards: {str(e)}")


def generate_quiz(client, video_id, num_questions=8, quiz_type="mixed"):
    """
    Generate educational quiz from video content using TwelveLabs analysis.
    
    Args:
        client: TwelveLabs client instance
        video_id: The unique identifier of the video
        num_questions: Number of quiz questions to generate (default: 8)
        quiz_type: Type of quiz - "multiple_choice", "true_false", "mixed" (default: "mixed")
    
    Returns:
        Dictionary with quiz questions and metadata
    """
    try:
        # Create specialized prompt for quiz generation
        if quiz_type == "multiple_choice":
            question_format = "multiple choice questions with 4 options (A, B, C, D)"
        elif quiz_type == "true_false":
            question_format = "true/false questions"
        else:  # mixed
            question_format = f"{num_questions//2} multiple choice and {num_questions//2} true/false questions"
        
        prompt = f"""Generate {num_questions} educational quiz questions from this video content.
Create {question_format}.

Format your response as a JSON structure:
{{
    "quiz": {{
        "title": "Quiz title based on video content",
        "instructions": "Brief instructions for taking the quiz",
        "questions": [
            {{
                "id": 1,
                "type": "multiple_choice" or "true_false",
                "question": "Clear question text",
                "options": ["A) Option 1", "B) Option 2", "C) Option 3", "D) Option 4"] (for multiple choice only),
                "correct_answer": "A" (for multiple choice) or true/false (for true/false),
                "explanation": "Why this answer is correct",
                "topic": "Topic area",
                "timestamp": "MM:SS (if relevant)"
            }}
        ]
    }},
    "answer_key": [
        {{
            "question_id": 1,
            "correct_answer": "A",
            "explanation": "Detailed explanation"
        }}
    ]
}}

Guidelines:
- Test understanding of key concepts from the video
- Make multiple choice options plausible but clearly distinguishable
- Include variety in question difficulty
- Provide clear explanations for correct answers
- Reference specific video moments when relevant
- Avoid trick questions - focus on genuine comprehension"""

        # Use TwelveLabs analyze function
        result = client.analyze(
            video_id=video_id,
            prompt=prompt,
            temperature=0.2  # Very low temperature for consistent quiz format
        )
        
        # Extract analysis text
        analysis_text = getattr(result, 'data', '')
        
        # Try to parse JSON from the response
        import json
        try:
            json_start = analysis_text.find('{')
            json_end = analysis_text.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                json_str = analysis_text[json_start:json_end]
                quiz_data = json.loads(json_str)
            else:
                # Fallback structure
                quiz_data = {
                    "quiz": {
                        "title": "Video Content Quiz",
                        "instructions": "Select the best answer for each question.",
                        "questions": []
                    },
                    "answer_key": []
                }
                
        except json.JSONDecodeError:
            # Create simple fallback quiz
            quiz_data = {
                "quiz": {
                    "title": "Video Content Quiz",
                    "instructions": "Answer based on the video content.",
                    "questions": [{
                        "id": 1,
                        "type": "true_false",
                        "question": "This video contains educational content worth studying.",
                        "correct_answer": True,
                        "explanation": "Based on the video analysis provided.",
                        "topic": "Video Overview"
                    }]
                },
                "answer_key": [{
                    "question_id": 1,
                    "correct_answer": True,
                    "explanation": "Based on the video analysis provided."
                }]
            }
        
        return {
            'quiz': quiz_data.get('quiz', {}),
            'answer_key': quiz_data.get('answer_key', []),
            'total_questions': len(quiz_data.get('quiz', {}).get('questions', [])),
            'quiz_type': quiz_type,
            'video_id': video_id,
            'id': getattr(result, 'id', 'unknown'),
            'usage': getattr(result, 'usage', {})
        }
        
    except Exception as e:
        raise Exception(f"Error generating quiz: {str(e)}")


def create_study_guide_pdf(video_title, flashcards_result=None, quiz_result=None, 
                          summary_result=None, chapters_result=None, highlights_result=None):
    """
    Create a comprehensive study guide PDF with flashcards, quizzes, and video analysis.
    
    Args:
        video_title: Title of the video
        flashcards_result: Result from generate_flashcards()
        quiz_result: Result from generate_quiz()
        summary_result: Result from generate_summary()
        chapters_result: Result from generate_chapters()
        highlights_result: Result from generate_highlights()
    
    Returns:
        Filename of the created PDF
    """
    try:
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
        from datetime import datetime
        
        # Clean video title for filename
        clean_title = "".join(c for c in video_title if c.isalnum() or c in (' ', '-', '_')).rstrip()
        clean_title = clean_title.replace(' ', '_')[:50]
        
        # Create filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"StudyGuide_{clean_title}_{timestamp}.pdf"
        
        # Create PDF document
        doc = SimpleDocTemplate(
            filename,
            pagesize=A4,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=18
        )
        
        # Get styles
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.darkblue
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor=colors.darkgreen
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=14,
            spaceAfter=8,
            spaceBefore=12,
            textColor=colors.darkred
        )
        
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=6,
            alignment=TA_JUSTIFY
        )
        
        # Build content
        content = []
        
        # Title page
        content.append(Paragraph("📚 Video Study Guide", title_style))
        content.append(Spacer(1, 20))
        content.append(Paragraph(f"<b>Video:</b> {video_title}", heading_style))
        content.append(Spacer(1, 10))
        content.append(Paragraph(f"<b>Generated:</b> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", body_style))
        content.append(Spacer(1, 10))
        content.append(Paragraph("<b>Created by:</b> HootQnA Video Analysis System", body_style))
        content.append(PageBreak())
        
        # Table of Contents
        content.append(Paragraph("📋 Table of Contents", title_style))
        content.append(Spacer(1, 20))
        
        toc_items = []
        if summary_result:
            toc_items.append("1. Video Summary")
        if chapters_result:
            toc_items.append("2. Chapter Breakdown")
        if highlights_result:
            toc_items.append("3. Key Highlights")
        if flashcards_result:
            toc_items.append("4. Study Flashcards")
        if quiz_result:
            toc_items.append("5. Practice Quiz")
            toc_items.append("6. Quiz Answer Key")
        
        for item in toc_items:
            content.append(Paragraph(item, body_style))
            content.append(Spacer(1, 8))
        
        content.append(PageBreak())
        
        # Video Summary Section
        if summary_result:
            content.append(Paragraph("📖 Video Summary", heading_style))
            content.append(Spacer(1, 12))
            
            if summary_result.get('summary'):
                content.append(Paragraph(summary_result['summary'], body_style))
            
            content.append(PageBreak())
        
        # Chapters Section
        if chapters_result and chapters_result.get('chapters'):
            content.append(Paragraph("📑 Chapter Breakdown", heading_style))
            content.append(Spacer(1, 12))
            
            for i, chapter in enumerate(chapters_result['chapters'], 1):
                content.append(Paragraph(f"Chapter {i}: {chapter.get('chapter_title', 'Untitled')}", subheading_style))
                
                # Time info
                start_time = seconds_to_mmss(chapter.get('start_sec', 0))
                end_time = seconds_to_mmss(chapter.get('end_sec', 0))
                content.append(Paragraph(f"<b>⏰ Time:</b> {start_time} - {end_time}", body_style))
                
                # Summary
                if chapter.get('chapter_summary'):
                    content.append(Paragraph(f"<b>📝 Summary:</b> {chapter['chapter_summary']}", body_style))
                
                content.append(Spacer(1, 12))
            
            content.append(PageBreak())
        
        # Highlights Section
        if highlights_result and highlights_result.get('highlights'):
            content.append(Paragraph("⭐ Key Highlights", heading_style))
            content.append(Spacer(1, 12))
            
            for i, highlight in enumerate(highlights_result['highlights'], 1):
                content.append(Paragraph(f"Highlight {i}: {highlight.get('highlight', 'Key Moment')}", subheading_style))
                
                # Time info
                start_time = seconds_to_mmss(highlight.get('start_sec', 0))
                end_time = seconds_to_mmss(highlight.get('end_sec', 0))
                content.append(Paragraph(f"<b>⏰ Time:</b> {start_time} - {end_time}", body_style))
                
                # Summary
                if highlight.get('highlight_summary'):
                    content.append(Paragraph(f"<b>📝 Details:</b> {highlight['highlight_summary']}", body_style))
                
                content.append(Spacer(1, 12))
            
            content.append(PageBreak())
        
        # Flashcards Section
        if flashcards_result and flashcards_result.get('flashcards'):
            content.append(Paragraph("🃏 Study Flashcards", heading_style))
            content.append(Spacer(1, 12))
            
            if flashcards_result.get('summary'):
                content.append(Paragraph(f"<b>Overview:</b> {flashcards_result['summary']}", body_style))
                content.append(Spacer(1, 12))
            
            for i, card in enumerate(flashcards_result['flashcards'], 1):
                # Create flashcard table
                flashcard_data = [
                    ['Question', card.get('question', 'No question available')],
                    ['Answer', card.get('answer', 'No answer available')]
                ]
                
                if card.get('topic'):
                    flashcard_data.insert(0, ['Topic', card['topic']])
                
                if card.get('timestamp'):
                    flashcard_data.append(['Timestamp', card['timestamp']])
                
                content.append(Paragraph(f"Flashcard {i}", subheading_style))
                
                table = Table(flashcard_data, colWidths=[1.5*inch, 4.5*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.lightblue),
                    ('TEXTCOLOR', (0, 0), (0, -1), colors.black),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 10),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ]))
                
                content.append(table)
                content.append(Spacer(1, 15))
            
            content.append(PageBreak())
        
        # Quiz Section
        if quiz_result and quiz_result.get('quiz', {}).get('questions'):
            quiz_data = quiz_result['quiz']
            
            content.append(Paragraph("📝 Practice Quiz", heading_style))
            content.append(Spacer(1, 12))
            
            if quiz_data.get('instructions'):
                content.append(Paragraph(f"<b>Instructions:</b> {quiz_data['instructions']}", body_style))
                content.append(Spacer(1, 12))
            
            for question in quiz_data['questions']:
                q_id = question.get('id', 1)
                content.append(Paragraph(f"Question {q_id}:", subheading_style))
                content.append(Paragraph(question.get('question', 'No question available'), body_style))
                
                if question.get('type') == 'multiple_choice' and question.get('options'):
                    for option in question['options']:
                        content.append(Paragraph(f"   {option}", body_style))
                elif question.get('type') == 'true_false':
                    content.append(Paragraph("   ○ True", body_style))
                    content.append(Paragraph("   ○ False", body_style))
                
                content.append(Spacer(1, 10))
            
            content.append(PageBreak())
            
            # Answer Key
            content.append(Paragraph("🔑 Quiz Answer Key", heading_style))
            content.append(Spacer(1, 12))
            
            for question in quiz_data['questions']:
                q_id = question.get('id', 1)
                correct_answer = question.get('correct_answer', 'Not available')
                explanation = question.get('explanation', '')
                
                content.append(Paragraph(f"Question {q_id}:", subheading_style))
                content.append(Paragraph(f"<b>Correct Answer:</b> {correct_answer}", body_style))
                
                if explanation:
                    content.append(Paragraph(f"<b>Explanation:</b> {explanation}", body_style))
                
                if question.get('timestamp'):
                    content.append(Paragraph(f"<b>Video Reference:</b> {question['timestamp']}", body_style))
                
                content.append(Spacer(1, 10))
        
        # Build PDF
        doc.build(content)
        
        return filename
        
    except Exception as e:
        raise Exception(f"Error creating study guide PDF: {str(e)}")


def send_pdf_to_discord(pdf_filename, message_text="Study Guide Generated! 📚"):
    """
    Send a PDF file to Discord channel via FastAPI bot endpoint.
    
    Args:
        pdf_filename: Path to the PDF file to send
        message_text: Optional message to accompany the PDF
    
    Returns:
        Dictionary with success status and message
    """
    try:
        # Validate Discord configuration
        if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID:
            return {
                "success": False,
                "message": "Discord configuration missing. Please set DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID in your .env file."
            }
        
        # Check if PDF file exists
        if not os.path.exists(pdf_filename):
            return {
                "success": False,
                "message": f"PDF file not found: {pdf_filename}"
            }
        
        # Get file size for display
        file_size = os.path.getsize(pdf_filename)
        file_size_mb = file_size / (1024 * 1024)
        
        # Prepare the request to FastAPI endpoint
        endpoint_url = f"{DISCORD_BOT_ENDPOINT}/send_pdf"
        
        # Prepare files and data for the request
        with open(pdf_filename, 'rb') as file:
            files = {
                'file': (os.path.basename(pdf_filename), file, 'application/pdf')
            }
            
            data = {
                'channel_id': DISCORD_CHANNEL_ID,
                'message': message_text,
                'bot_token': DISCORD_BOT_TOKEN
            }
            
            # Send POST request to FastAPI bot endpoint
            response = requests.post(endpoint_url, files=files, data=data, timeout=30)
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                return {
                    "success": True,
                    "message": f"✅ PDF sent to Discord successfully! ({file_size_mb:.1f} MB)",
                    "file_size": file_size_mb
                }
            else:
                return {
                    "success": False,
                    "message": f"Discord API error: {result.get('message', 'Unknown error')}"
                }
        else:
            return {
                "success": False,
                "message": f"FastAPI endpoint error: HTTP {response.status_code} - {response.text}"
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "message": "❌ Cannot connect to Discord bot endpoint. Make sure your FastAPI bot is running."
        }
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": "⏱️ Request timeout. The Discord bot may be slow to respond."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"❌ Error sending to Discord: {str(e)}"
        }


def check_discord_bot_status():
    """
    Check if the Discord bot FastAPI endpoint is available.
    
    Returns:
        Dictionary with status information
    """
    try:
        if not DISCORD_BOT_ENDPOINT:
            return {
                "online": False,
                "message": "Discord bot endpoint not configured"
            }
        
        # Try to ping the health endpoint
        health_url = f"{DISCORD_BOT_ENDPOINT}/health"
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            return {
                "online": True,
                "message": "✅ Discord bot is online and ready",
                "endpoint": DISCORD_BOT_ENDPOINT
            }
        else:
            return {
                "online": False,
                "message": f"Discord bot responded with status {response.status_code}"
            }
            
    except requests.exceptions.ConnectionError:
        return {
            "online": False,
            "message": "❌ Discord bot is offline or unreachable"
        }
    except Exception as e:
        return {
            "online": False,
            "message": f"Error checking bot status: {str(e)}"
        }


def get_discord_config_status():
    """
    Check Discord configuration status.
    
    Returns:
        Dictionary with configuration status
    """
    bot_token_set = bool(DISCORD_BOT_TOKEN and DISCORD_BOT_TOKEN != "your_discord_bot_token_here")
    channel_id_set = bool(DISCORD_CHANNEL_ID and DISCORD_CHANNEL_ID != "your_discord_channel_id_here")
    endpoint_set = bool(DISCORD_BOT_ENDPOINT)
    
    fully_configured = bot_token_set and channel_id_set and endpoint_set
    
    config_status = {
        "configured": fully_configured,
        "bot_token_set": bot_token_set,
        "channel_id_set": channel_id_set,
        "endpoint_set": endpoint_set,
        "message": "All Discord settings configured" if fully_configured else "Missing Discord configuration in .env file"
    }
    
    return config_status