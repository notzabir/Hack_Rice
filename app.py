import streamlit as st
import tempfile
import os
from datetime import datetime
from twelvelabs import TwelveLabs
import streamlit_auth0_component as sac
from auth_config import AUTH0_DOMAIN, AUTH0_CLIENT_ID
import database as db
import logging

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Initialize the database
db.init_db()

try:
    from utils import (
        API_KEY, process_video, fetch_existing_videos,
        get_video_url, get_hls_player_html, generate_timestamps,
        download_video_segment, create_video_segments,
        search_video_content, create_qa_video_snippet, 
        format_qa_results, format_qa_results_with_summary,
        get_video_qa_capabilities, seconds_to_mmss,
        generate_summary, generate_chapters, generate_highlights,
        generate_open_analysis, create_analysis_video_snippet,
        create_hls_snippet_alternative
    )
except ValueError as e:
    st.error(f"Configuration Error: {str(e)}")
    st.stop()
except Exception as e:
    st.error(f"Error importing utilities: {str(e)}")
    st.stop()

import uuid 

def main():
    st.set_page_config(
        page_title="🎬 HootQnA - AI Video Analysis Platform", 
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Auth0 login
    auth_info = sac.login_button(
        clientId=AUTH0_CLIENT_ID,
        domain=AUTH0_DOMAIN,
    )

    if not auth_info:
        st.warning("Please log in to access the application.")
        st.stop()

    st.session_state.user_db_id = db.get_or_create_user(auth_info)

    st.sidebar.success(f"Welcome, {auth_info['name']}!")
    
    with st.sidebar:
        sac.logout_button()

    run_app()

def run_app():
    # Using st.tabs for navigation
    tab1, tab2, tab3, tab4 = st.tabs(["Upload Video", "My Videos", "Video Analysis", "Q&A"])

    with tab1:
        upload_and_process_video()

    with tab2:
        display_my_videos()

    with tab3:
        if 'video_id' in st.session_state and st.session_state.video_id:
            display_video_analysis_section()
        else:
            st.info("Please select a video from the 'My Videos' tab to perform analysis.")

    with tab4:
        display_qa_interface()

def display_my_videos():
    st.header("My Processed Videos")
    if 'user_db_id' not in st.session_state:
        st.error("User not logged in properly.")
        return

    user_videos = db.get_user_videos(st.session_state.user_db_id)

    if not user_videos:
        st.info("You haven't processed any videos yet. Go to the 'Upload Video' tab to get started.")
    else:
        video_options = {f"{v['filename']} ({v['status']})": v['id'] for v in user_videos}
        selected_video_display = st.selectbox("Choose a video to analyze", options=video_options.keys())

        if selected_video_display:
            db_video_id = video_options[selected_video_display]
            video_data = db.get_video_by_id(db_video_id)
            
            if video_data and video_data['status'] == 'ready':
                st.session_state.video_id = video_data['twelvelabs_video_id']
                st.session_state.db_video_id = db_video_id # Store internal DB id
                st.success(f"Selected video: **{video_data['filename']}**")
                st.write("You can now generate summaries, chapters, or ask questions about this video in the other tabs.")
            elif video_data:
                st.warning(f"This video is currently in '{video_data['status']}' state and cannot be analyzed yet.")
 

def log_error(error_type, error_message, context=None, recovery_suggestions=None):
    error_entry = {
        'timestamp': st.session_state.get('current_time', 'unknown'),
        'type': error_type,
        'message': error_message,
        'context': context,
        'recovery_suggestions': recovery_suggestions or []
    }
    st.session_state.error_log.append(error_entry)
    st.session_state.last_error = error_entry
    return error_entry

def display_enhanced_error(error_type, error_message, recovery_suggestions=None):
    st.error(f"Error: {error_type} - {error_message}")
    
    if recovery_suggestions:
        with st.expander("Troubleshooting & Recovery Options"):
            for i, suggestion in enumerate(recovery_suggestions, 1):
                st.write(f"{i}. {suggestion}")
    
    log_error(error_type, error_message, recovery_suggestions=recovery_suggestions)

def get_recovery_suggestions(error_type):
    suggestions = {
        'upload_error': [
            "Check if the video file is not corrupted",
            "Ensure the video format is supported (MP4, AVI, MOV)",
            "Verify the video file size is under 1GB",
            "Try uploading a smaller video segment first",
            "Check your internet connection"
        ],
        'api_error': [
            "Check your TwelveLabs API key in the .env file",
            "Verify your INDEX_ID is correct",
            "Ensure you have sufficient API credits",
            "Try refreshing the page",
            "Contact support if the issue persists"
        ],
        'processing_error': [
            "Wait a few minutes and try again",
            "Check if the video is still being processed",
            "Try with a shorter video",
            "Verify your internet connection",
            "Clear browser cache and reload"
        ],
        'search_error': [
            "Wait for video indexing to complete",
            "Try a different search query",
            "Check if the video was uploaded successfully",
            "Refresh the page and try again"
        ]
    }
    return suggestions.get(error_type, ["Try refreshing the page", "Contact support if the issue persists"])

def format_timestamps_for_youtube(timestamps):
    if not timestamps:
        return ""
    
    lines = timestamps.strip().split('\n')
    youtube_format = []
    
    for line in lines:
        if '-' in line:
            time_part, title_part = line.split('-', 1)
            time_part = time_part.strip()
            title_part = title_part.strip()
            youtube_format.append(f"{time_part} - {title_part}")
    
    return '\n'.join(youtube_format)

def export_to_json(data, filename="export"):
    import json
    from datetime import datetime
    
    export_data = {
        'export_timestamp': datetime.now().isoformat(),
        'video_id': st.session_state.get('video_id'),
        'timestamps': st.session_state.get('timestamps'),
        'qa_results': data.get('qa_results', []),
        'chapters': data.get('chapters', []),
        'highlights': data.get('highlights', [])
    }
    
    return json.dumps(export_data, indent=2)

def export_to_csv(data, filename="export"):
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Type', 'Timestamp', 'Title/Query', 'Content', 'Confidence'])
    
    if st.session_state.get('timestamps'):
        for line in st.session_state.timestamps.split('\n'):
            if '-' in line:
                time_part, title_part = line.split('-', 1)
                writer.writerow(['Timestamp', time_part.strip(), title_part.strip(), '', ''])
    
    for result in data.get('qa_results', []):
        writer.writerow([
            'QA Result', 
            f"{result.get('start', '')}-{result.get('end', '')}", 
            result.get('query', ''), 
            result.get('text', ''), 
            result.get('confidence', '')
        ])
    
    return output.getvalue()

def create_export_button(data, export_type="youtube", label="Export"):
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if export_type == "youtube":
            content = format_timestamps_for_youtube(st.session_state.get('timestamps', ''))
            st.text_area("YouTube Format (Copy this to your video description):", 
                        value=content, height=100, key=f"export_youtube_{uuid.uuid4()}")
        elif export_type == "json":
            content = export_to_json(data)
            st.text_area("JSON Export:", value=content, height=200, key=f"export_json_{uuid.uuid4()}")
        elif export_type == "csv":
            content = export_to_csv(data)
            st.text_area("CSV Export:", value=content, height=200, key=f"export_csv_{uuid.uuid4()}")
    
    with col2:
        if st.button(f"Copy {export_type.upper()}", key=f"copy_{export_type}_{uuid.uuid4()}"):
            st.components.v1.html(f"""
                <script>
                navigator.clipboard.writeText(`{content.replace('`', '\\`')}`).then(function() {{
                    console.log('Copied to clipboard!');
                }});
                </script>
            """, height=0)
            st.success(f"Copied {export_type.upper()} format to clipboard!")
            
            st.session_state.export_history.append({
                'timestamp': str(datetime.now()),
                'type': export_type,
                'video_id': st.session_state.get('video_id')
            })
    
    with col3:
        if export_type == "json":
            st.download_button(
                label=f"Download JSON",
                data=content,
                file_name=f"video_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key=f"download_json_{uuid.uuid4()}"
            )
        elif export_type == "csv":
            st.download_button(
                label=f"Download CSV",
                data=content,
                file_name=f"video_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=f"download_csv_{uuid.uuid4()}"
            ) 

def log_error(error_type, error_message, context=None, recovery_suggestions=None):
    error_entry = {
        'timestamp': st.session_state.get('current_time', 'unknown'),
        'type': error_type,
        'message': error_message,
        'context': context,
        'recovery_suggestions': recovery_suggestions or []
    }
    st.session_state.error_log.append(error_entry)
    st.session_state.last_error = error_entry
    return error_entry

def display_enhanced_error(error_type, error_message, recovery_suggestions=None):
    st.error(f"Error: {error_type} - {error_message}")
    
    if recovery_suggestions:
        with st.expander("Troubleshooting & Recovery Options"):
            for i, suggestion in enumerate(recovery_suggestions, 1):
                st.write(f"{i}. {suggestion}")
    
    log_error(error_type, error_message, recovery_suggestions=recovery_suggestions)

def get_recovery_suggestions(error_type):
    suggestions = {
        'upload_error': [
            "Check if the video file is not corrupted",
            "Ensure the video format is supported (MP4, AVI, MOV)",
            "Verify the video file size is under 1GB",
            "Try uploading a smaller video segment first",
            "Check your internet connection"
        ],
        'api_error': [
            "Check your TwelveLabs API key in the .env file",
            "Verify your INDEX_ID is correct",
            "Ensure you have sufficient API credits",
            "Try refreshing the page",
            "Contact support if the issue persists"
        ],
        'processing_error': [
            "Wait a few minutes and try again",
            "Check if the video is still being processed",
            "Try with a shorter video",
            "Verify your internet connection",
            "Clear browser cache and reload"
        ],
        'search_error': [
            "Wait for video indexing to complete",
            "Try a different search query",
            "Check if the video was uploaded successfully",
            "Refresh the page and try again"
        ]
    }
    return suggestions.get(error_type, ["Try refreshing the page", "Contact support if the issue persists"])

def format_timestamps_for_youtube(timestamps):
    if not timestamps:
        return ""
    
    lines = timestamps.strip().split('\n')
    youtube_format = []
    
    for line in lines:
        if '-' in line:
            time_part, title_part = line.split('-', 1)
            time_part = time_part.strip()
            title_part = title_part.strip()
            youtube_format.append(f"{time_part} - {title_part}")
    
    return '\n'.join(youtube_format)

def export_to_json(data, filename="export"):
    import json
    from datetime import datetime
    
    export_data = {
        'export_timestamp': datetime.now().isoformat(),
        'video_id': st.session_state.get('video_id'),
        'timestamps': st.session_state.get('timestamps'),
        'qa_results': data.get('qa_results', []),
        'chapters': data.get('chapters', []),
        'highlights': data.get('highlights', [])
    }
    
    return json.dumps(export_data, indent=2)

def export_to_csv(data, filename="export"):
    import csv
    import io
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    writer.writerow(['Type', 'Timestamp', 'Title/Query', 'Content', 'Confidence'])
    
    if st.session_state.get('timestamps'):
        for line in st.session_state.timestamps.split('\n'):
            if '-' in line:
                time_part, title_part = line.split('-', 1)
                writer.writerow(['Timestamp', time_part.strip(), title_part.strip(), '', ''])
    
    for result in data.get('qa_results', []):
        writer.writerow([
            'QA Result', 
            f"{result.get('start', '')}-{result.get('end', '')}", 
            result.get('query', ''), 
            result.get('text', ''), 
            result.get('confidence', '')
        ])
    
    return output.getvalue()

def create_export_button(data, export_type="youtube", label="Export"):
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        if export_type == "youtube":
            content = format_timestamps_for_youtube(st.session_state.get('timestamps', ''))
            st.text_area("YouTube Format (Copy this to your video description):", 
                        value=content, height=100, key=f"export_youtube_{uuid.uuid4()}")
        elif export_type == "json":
            content = export_to_json(data)
            st.text_area("JSON Export:", value=content, height=200, key=f"export_json_{uuid.uuid4()}")
        elif export_type == "csv":
            content = export_to_csv(data)
            st.text_area("CSV Export:", value=content, height=200, key=f"export_csv_{uuid.uuid4()}")
    
    with col2:
        if st.button(f"Copy {export_type.upper()}", key=f"copy_{export_type}_{uuid.uuid4()}"):
            st.components.v1.html(f"""
                <script>
                navigator.clipboard.writeText(`{content.replace('`', '\\`')}`).then(function() {{
                    console.log('Copied to clipboard!');
                }});
                </script>
            """, height=0)
            st.success(f"Copied {export_type.upper()} format to clipboard!")
            
            st.session_state.export_history.append({
                'timestamp': str(datetime.now()),
                'type': export_type,
                'video_id': st.session_state.get('video_id')
            })
    
    with col3:
        if export_type == "json":
            st.download_button(
                label=f"Download JSON",
                data=content,
                file_name=f"video_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                key=f"download_json_{uuid.uuid4()}"
            )
        elif export_type == "csv":
            st.download_button(
                label=f"Download CSV",
                data=content,
                file_name=f"video_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                key=f"download_csv_{uuid.uuid4()}"
            ) 

st.set_page_config(
    page_title="🎬 HootQnA - AI Video Analysis Platform", 
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_css(file_name):
    with open(file_name) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css("style.css")

st.markdown("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
</head>
""", unsafe_allow_html=True)

# Streamlit Page Header
st.markdown("<h1 style='text-align: center; color: #f8fafc; font-weight: 600;'>HootQnA AI Video Analysis Platform</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666; font-size: 18px; margin-bottom: 2rem;'>Advanced video processing, timestamp generation, and intelligent content analysis</p>", unsafe_allow_html=True)

# Keyboard shortcuts help
with st.expander("Keyboard Shortcuts", expanded=False):
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        **Navigation:**
        - `Ctrl + U` - Upload tab
        - `Ctrl + Q` - Q&A tab
        - `Ctrl + S` - Focus search
        """)
    with col2:
        st.markdown("""
        **Actions:**
        - `Ctrl + E` - Export timestamps
        - `Esc` - Clear search
        - `F5` - Refresh page
        """)

st.markdown("---")

# Initialize session state with progress persistence
def initialize_session_state():
    """Initialize session state with enhanced progress persistence."""
    # Core video data
    if 'timestamps' not in st.session_state:
        st.session_state.timestamps = None
    if 'video_id' not in st.session_state:
        st.session_state.video_id = None
    if 'video_segments' not in st.session_state:
        st.session_state.video_segments = []
    if 'video_url' not in st.session_state:
        st.session_state.video_url = None
    if 'qa_results' not in st.session_state:
        st.session_state.qa_results = []
    if 'qa_snippets' not in st.session_state:
        st.session_state.qa_snippets = []
    if 'chapters_result' not in st.session_state:
        st.session_state.chapters_result = None
    if 'highlights_result' not in st.session_state:
        st.session_state.highlights_result = None
    if 'chapter_snippets' not in st.session_state:
        st.session_state.chapter_snippets = []
    if 'highlight_snippets' not in st.session_state:
        st.session_state.highlight_snippets = []
    
    # Progress persistence
    if 'processing_status' not in st.session_state:
        st.session_state.processing_status = {}
    if 'last_upload_info' not in st.session_state:
        st.session_state.last_upload_info = None
    if 'video_metadata' not in st.session_state:
        st.session_state.video_metadata = {}
    if 'search_history' not in st.session_state:
        st.session_state.search_history = []
    if 'export_history' not in st.session_state:
        st.session_state.export_history = []
    
    # Batch operations
    if 'batch_queue' not in st.session_state:
        st.session_state.batch_queue = []
    if 'batch_results' not in st.session_state:
        st.session_state.batch_results = {}
    if 'batch_processing' not in st.session_state:
        st.session_state.batch_processing = False
    
    # Error tracking
    if 'error_log' not in st.session_state:
        st.session_state.error_log = []
    if 'last_error' not in st.session_state:
        st.session_state.last_error = None

# Initialize session state
initialize_session_state()


def display_qa_snippet(file_name, query, snippet_info, snippet_index):
    """Display a QA video snippet with metadata."""
    if os.path.exists(file_name):
        st.write(f"### Query: {query}")
        st.write(f"**Timeframe:** {snippet_info['start_time_str']} - {snippet_info['end_time_str']} ({snippet_info['duration']:.1f}s)")
        st.write(f"**Confidence:** {snippet_info['confidence'] * 100:.1f}%")
        if snippet_info.get('text'):
            st.write(f"**Content Preview:** {snippet_info['text'][:150]}...")
        
        st.video(file_name)
        
        with open(file_name, "rb") as file:
            file_contents = file.read()
        
        unique_key = f"download_qa_{snippet_index}_{uuid.uuid4()}"
        st.download_button(
            label=f"Download QA Snippet",
            data=file_contents,
            file_name=file_name,
            mime="video/mp4",
            key=unique_key
        )
        st.markdown("---")
    else:
        st.warning(f"QA snippet file {file_name} not found.")


def process_qa_search():
    """Process QA search and create video snippets."""
    
    # Search scope selection
    st.subheader("Search Scope")
    
    col1, col2 = st.columns([1, 1])
    with col1:
        search_scope = st.radio(
            "Where to search:",
            ["Current video only", "All videos in index"],
            key="search_scope",
            help="Choose whether to search only the current video or across all videos in your TwelveLabs index"
        )
    
    with col2:
        if search_scope == "Current video only" and not st.session_state.video_id:
            st.error("No video selected. Please upload or select a video first, or choose 'All videos in index'.")
            return
        elif search_scope == "All videos in index":
            st.info("Searching across all videos in your TwelveLabs index")
    
    # Check search readiness for current video (if applicable)
    if search_scope == "Current video only":
        try:
            client = TwelveLabs(api_key=API_KEY)
            capabilities = get_video_qa_capabilities(client, st.session_state.video_id)
            
            if capabilities['ready_for_search']:
                st.success("Video is ready for Q&A search!")
            else:
                st.warning("Video is still being processed for search. This can take a few minutes after upload.")
                st.info("""
                **What's happening?**
                - Your video has been uploaded successfully
                - Basic processing (timestamps) is complete  
                - Search indexing is still in progress
                
                **What to do:**
                - Wait 2-5 minutes and refresh this page
                - You can still use the timestamp generation feature
                - Or try searching "All videos in index" if you have other videos
                """)
        except Exception as e:
            st.warning(f"Could not check search status: {str(e)}")
            capabilities = {'ready_for_search': True}  # Assume it's ready if we can't check
    else:
        capabilities = {'ready_for_search': True}  # Index search should always be available
    
    query = st.text_input("Ask a question about the video(s):", 
                         placeholder="e.g., 'What are the main topics discussed?', 'Show me the introduction', 'Find product demonstrations'",
                         disabled=not capabilities['ready_for_search'])
    
    # Analysis options
    st.subheader("Analysis Options")
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        max_results = st.selectbox("Max Results:", [3, 5, 10, 15], index=1, 
                                 disabled=not capabilities['ready_for_search'])
    
    with col2:
        analysis_mode = st.selectbox(
            "Analysis Type:",
            ["Standard Search", "Enhanced Analysis", "With Video Summary"],
            index=1,
            disabled=not capabilities['ready_for_search'],
            help="Enhanced Analysis includes detailed content analysis for each segment"
        )
    
    with col3:
        if analysis_mode == "Enhanced Analysis":
            st.info("Includes detailed analysis of each segment")
        elif analysis_mode == "With Video Summary":
            st.info("Includes video summary + highlights + detailed segments")
        else:
            st.info("Fast search with basic content preview")
    
    search_disabled = not capabilities['ready_for_search'] or not query
        
    if query and st.button("Search Video(s)", key="search_qa_button", disabled=search_disabled):
        try:
            with st.spinner("Searching video content and generating analysis..."):
                client = TwelveLabs(api_key=API_KEY)
                
                # Determine video_id based on search scope
                target_video_id = st.session_state.video_id if search_scope == "Current video only" else None
                
                # Double-check readiness for current video search
                if search_scope == "Current video only":
                    capabilities = get_video_qa_capabilities(client, st.session_state.video_id)
                    if not capabilities['ready_for_search']:
                        st.error("Video search indexing is not complete yet. Please wait a few more minutes.")
                        st.info("💡 Tip: Try searching 'All videos in index' or refresh the page to check if indexing has completed.")
                        return
                
                # Search for relevant segments
                search_results = search_video_content(client, target_video_id, query, max_results)
                
                if not search_results:
                    search_scope_text = "the current video" if search_scope == "Current video only" else "any videos in your index"
                    st.info(f"No relevant segments found for: '{query}' in {search_scope_text}")
                    return
                
                st.session_state.qa_results = search_results
                
                # Display search results based on analysis mode
                scope_text = "current video" if search_scope == "Current video only" else "index"
                st.success(f"Found {len(search_results)} relevant segments in {scope_text}!")
                
                # Choose formatting based on analysis mode
                if analysis_mode == "With Video Summary":
                    formatted_results = format_qa_results_with_summary(search_results, query, client)
                elif analysis_mode == "Enhanced Analysis":
                    formatted_results = format_qa_results(search_results, query, client, include_rich_analysis=True)
                else:  # Standard Search
                    formatted_results = format_qa_results(search_results, query, client, include_rich_analysis=False)
                
                st.markdown(formatted_results)
                
                # Show additional analysis options
                if analysis_mode in ["Enhanced Analysis", "With Video Summary"]:
                    st.info("Enhanced analysis powered by TwelveLabs multimodal understanding")
                
                # Option to create video snippets
                # Note: Can only create snippets if we have video URLs
                if search_scope == "Current video only" and st.session_state.video_url:
                    if st.button("Create Video Snippets", key="create_qa_snippets_button"):
                        create_qa_snippets(query, search_results)
                elif search_scope == "Current video only" and not st.session_state.video_url:
                    st.info("Video snippets require streaming URL. Try refreshing the video URL first.")
                elif search_scope == "All videos in index":
                    st.info("To create video snippets, search within a specific video that has streaming enabled.")
                    
        except Exception as e:
            st.error(f"Error during search: {str(e)}")
def create_qa_snippets(query, search_results):
    """Create video snippets from search results."""
    try:
        with st.spinner("Creating video snippets..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            st.session_state.qa_snippets = []  # Reset QA snippets
            
            for i, segment in enumerate(search_results, 1):
                status_text.text(f"Creating snippet {i}/{len(search_results)}...")
                
                # Create video snippet
                snippet_file = create_qa_video_snippet(
                    st.session_state.video_url,
                    segment['start_time'],
                    segment['end_time'],
                    query,
                    i
                )
                
                # Prepare snippet info for display
                snippet_info = {
                    'start_time_str': f"{int(segment['start_time'])//60:02d}:{int(segment['start_time'])%60:02d}",
                    'end_time_str': f"{int(segment['end_time'])//60:02d}:{int(segment['end_time'])%60:02d}",
                    'duration': segment['duration'],
                    'confidence': segment.get('score', segment.get('confidence', 0)),
                    'text': segment.get('text', '')
                }
                
                st.session_state.qa_snippets.append((snippet_file, query, snippet_info))
                
                progress = i / len(search_results)
                progress_bar.progress(progress)
            
            progress_bar.progress(1.0)
            status_text.text("All QA snippets created!")
            
    except Exception as e:
        st.error(f"Error creating QA snippets: {str(e)}")


def display_video_analysis_section():
    """Display standalone video analysis options for the current video."""
    st.markdown("---")
    st.subheader("Video Analysis & Insights")
    st.write("Get comprehensive analysis of your current video")
    
    if not st.session_state.video_id:
        return
    
    # Analysis options
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("Generate Summary", key="gen_summary_btn"):
            db_video_id = st.session_state.get('db_video_id')
            if not db_video_id:
                st.error("No database video ID found in session state.")
                return

            summary_data = db.get_analysis(db_video_id, "summary")
            if summary_data:
                st.subheader("Video Summary")
                st.write(summary_data['summary'])
            else:
                try:
                    with st.spinner("Generating video summary..."):
                        client = TwelveLabs(api_key=API_KEY)
                        summary_result = generate_summary(client, st.session_state.video_id)
                        db.save_analysis(db_video_id, "summary", summary_result)
                        st.subheader("Video Summary")
                        st.write(summary_result['summary'])
                except Exception as e:
                    st.error(f"Error generating summary: {str(e)}")
    
    with col2:
        if st.button("Generate Chapters", key="gen_chapters_btn"):
            db_video_id = st.session_state.get('db_video_id')
            if not db_video_id:
                st.error("No database video ID found in session state.")
                return
            
            chapters_data = db.get_analysis(db_video_id, "chapters")
            if chapters_data:
                st.subheader("Video Chapters")
                for chapter in chapters_data['chapters']:
                    st.write(f"**{chapter['chapter_title']}**")
                    st.write(f"_{seconds_to_mmss(chapter['start_sec'])} - {seconds_to_mmss(chapter['end_sec'])}_")
                    st.write(chapter['chapter_summary'])
                    st.markdown("---")
            else:
                try:
                    with st.spinner("Generating video chapters..."):
                        client = TwelveLabs(api_key=API_KEY)
                        chapters_result = generate_chapters(client, st.session_state.video_id)
                        db.save_analysis(db_video_id, "chapters", chapters_result)
                        st.subheader("Video Chapters")
                        for chapter in chapters_result['chapters']:
                            st.write(f"**{chapter['chapter_title']}**")
                            st.write(f"_{seconds_to_mmss(chapter['start_sec'])} - {seconds_to_mmss(chapter['end_sec'])}_")
                            st.write(chapter['chapter_summary'])
                            st.markdown("---")
                except Exception as e:
                    st.error(f"Error generating chapters: {str(e)}")
    
    with col3:
        if st.button("Generate Highlights", key="gen_highlights_btn"):
            db_video_id = st.session_state.get('db_video_id')
            if not db_video_id:
                st.error("No database video ID found in session state.")
                return

            highlights_data = db.get_analysis(db_video_id, "highlights")
            if highlights_data:
                st.subheader("Video Highlights")
                for highlight in highlights_data['highlights']:
                    st.write(f"**{highlight['highlight']}**")
                    st.write(f"_{seconds_to_mmss(highlight['start_sec'])} - {seconds_to_mmss(highlight['end_sec'])}_")
                    st.markdown("---")
            else:
                try:
                    with st.spinner("Generating video highlights..."):
                        client = TwelveLabs(api_key=API_KEY)
                        highlights_result = generate_highlights(client, st.session_state.video_id)
                        db.save_analysis(db_video_id, "highlights", highlights_result)
                        st.subheader("Video Highlights")
                        for highlight in highlights_result['highlights']:
                            st.write(f"**{highlight['highlight']}**")
                            st.write(f"_{seconds_to_mmss(highlight['start_sec'])} - {seconds_to_mmss(highlight['end_sec'])}_")
                            st.markdown("---")
                except Exception as e:
                    st.error(f"Error generating highlights: {str(e)}")
    
    # Custom analysis section
    st.subheader("Custom Analysis")
    custom_prompt = st.text_area(
        "Enter custom analysis prompt:",
        placeholder="e.g., 'Analyze the emotional tone of this video', 'List all products mentioned', 'Identify key learning objectives'",
        height=100
    )
    
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Analyze", key="custom_analysis_btn", disabled=not custom_prompt):
            db_video_id = st.session_state.get('db_video_id')
            if not db_video_id:
                st.error("No database video ID found in session state.")
                return
            
            analysis_type = f"custom_{custom_prompt[:50].replace(' ', '_')}"
            custom_analysis = db.get_analysis(db_video_id, analysis_type)

            if custom_analysis:
                st.subheader("Custom Analysis Results")
                st.write(custom_analysis['analysis'])
            else:
                try:
                    with st.spinner("Performing custom analysis..."):
                        client = TwelveLabs(api_key=API_KEY)
                        analysis_result = generate_open_analysis(
                            client, 
                            st.session_state.video_id, 
                            custom_prompt, 
                            temperature=0.3
                        )
                        db.save_analysis(db_video_id, analysis_type, analysis_result)
                        st.subheader("Custom Analysis Results")
                        st.write(analysis_result['analysis'])
                except Exception as e:
                    st.error(f"Error performing custom analysis: {str(e)}")
    
    with col2:
        st.info("**Analysis Tips:**\n- Be specific in your prompts\n- Ask about content, themes, or patterns\n- Request summaries for specific audiences\n- Analyze emotional tone or sentiment")



def display_qa_interface():
    """Main QA interface display function."""
    st.subheader("Video Q&A Interface")
    st.write("Ask questions about your videos and get relevant segments!")
    
    # Add helpful info about TwelveLabs search
    with st.expander("How TwelveLabs Video Search Works"):
        st.markdown("""
        **TwelveLabs Built-in Intelligence:**
        
        **No Manual Setup Required**: TwelveLabs automatically creates embeddings and vector indices when you upload videos
        
        **Multi-modal Search**: Searches across:
        - **Visual content**: Objects, scenes, actions, people
        - **Audio content**: Speech, music, sounds, conversations  
        - **Text content**: Any text visible in the video
        
        **Search Scope Options:**
        1. **Current Video Only**: Search within the specific video you've selected/uploaded
        2. **All Videos in Index**: Search across ALL videos in your TwelveLabs index
        
        **Query Examples:**
        - "Show me when people are talking"
        - "Find scenes with cars"
        - "Where is music playing?"
        - "Show me the product demonstration"
        - "Find the person wearing red"
        - "Locate discussions about pricing"
        
        **Multi-Video Benefits:**
        - Find content across your entire video library
        - Compare similar content between videos
        - Discover patterns across different videos
        - Access comprehensive search results
        """)
    
    # QA Search Interface
    process_qa_search()
    
    # Add video analysis section for current video
    if st.session_state.video_id:
        display_video_analysis_section()
    
    # Display created QA snippets
    if st.session_state.qa_snippets:
        st.subheader("Q&A Video Snippets")
        for index, (file_name, query, snippet_info) in enumerate(st.session_state.qa_snippets):
            display_qa_snippet(file_name, query, snippet_info, index)
        
        # Clear QA snippets button
        if st.button("Clear all QA snippets", key="clear_qa_snippets_button"):
            for file_name, _, _ in st.session_state.qa_snippets:
                if os.path.exists(file_name):
                    os.remove(file_name)
            st.session_state.qa_snippets = []
            st.session_state.qa_results = []
            st.success("All QA snippet files have been cleared.")
            st.experimental_rerun()
    
    # Show helpful message when no video is selected but interface is accessible
    if not st.session_state.video_id:
        st.info("""
        **Pro Tip**: Even without a specific video selected, you can:
        - Search across **all videos in your index** using the "All videos in index" option
        - Find content from any video in your TwelveLabs library
        - Upload a new video in the **"Upload Video"** tab
        - Select an existing video in the **"Select Existing"** tab
        """)


# Function to Display the Segment and also Download
def display_segment(file_name, description, segment_index):
    if os.path.exists(file_name):
        st.write(f"### {description}")
        st.video(file_name)
        with open(file_name, "rb") as file:
            file_contents = file.read()
        unique_key = f"download_{segment_index}_{uuid.uuid4()}"
        st.download_button(
            label=f"Download: {description}",
            data=file_contents,
            file_name=file_name,
            mime="video/mp4",
            key=unique_key
        )
        st.markdown("---")
    else:
        st.warning(f"File {file_name} not found. It may have been deleted or moved.")


# Function to process the segment
def process_and_display_segments():
    if not st.session_state.video_url:
        st.error("Video URL not found. Please reprocess the video.")
        return

    segment_generator = create_video_segments(st.session_state.video_url, st.session_state.timestamps)

    progress_bar = st.progress(0)
    status_text = st.empty()

    st.session_state.video_segments = []  # Reset video segments
    total_segments = len(st.session_state.timestamps.split('\n'))

    for i, (file_name, description) in enumerate(segment_generator, 1):
        st.session_state.video_segments.append((file_name, description))
        display_segment(file_name, description, i-1)  # Pass the index here
        progress = i / total_segments
        progress_bar.progress(progress)
        status_text.text(f"Processing segment {i}/{total_segments}...")

    progress_bar.progress(1.0)
    status_text.text("All segments processed!")


# Uplaoding feature and the processing of the video
# Batch Processing Functions
def add_to_batch_queue(file_info):
    """Add a video file to the batch processing queue."""
    batch_item = {
        'id': str(uuid.uuid4()),
        'filename': file_info['filename'],
        'size': file_info['size'],
        'type': file_info['type'],
        'status': 'queued',
        'video_id': None,
        'timestamps': None,
        'error': None,
        'progress': 0
    }
    st.session_state.batch_queue.append(batch_item)
    return batch_item['id']

def process_batch_queue():
    """Process all videos in the batch queue."""
    if not st.session_state.batch_queue:
        return
    
    st.session_state.batch_processing = True
    client = TwelveLabs(api_key=API_KEY)
    
    for i, item in enumerate(st.session_state.batch_queue):
        if item['status'] != 'queued':
            continue
            
        try:
            item['status'] = 'processing'
            item['progress'] = 25
            
            # Here you would process the actual file
            # For now, we'll simulate processing
            timestamps, video_id = "00:00-Sample Chapter", f"video_{item['id'][:8]}"
            
            item['video_id'] = video_id
            item['timestamps'] = timestamps
            item['status'] = 'completed'
            item['progress'] = 100
            
            st.session_state.batch_results[item['id']] = {
                'video_id': video_id,
                'timestamps': timestamps,
                'filename': item['filename']
            }
            
        except Exception as e:
            item['status'] = 'error'
            item['error'] = str(e)
            display_enhanced_error('Batch Processing Error', str(e), 
                                 get_recovery_suggestions('processing_error'))

    st.session_state.batch_processing = False

def display_batch_queue():
    """Display the current batch processing queue."""
    if not st.session_state.batch_queue:
        return
    
    st.subheader("Batch Processing Queue")
    
    for item in st.session_state.batch_queue:
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        
        with col1:
            st.write(f"{item['filename']}")
            
        with col2:
            if item['status'] == 'queued':
                st.write("Queued")
            elif item['status'] == 'processing':
                st.progress(item['progress'] / 100)
            elif item['status'] == 'completed':
                st.write("Completed")
            elif item['status'] == 'error':
                st.write("Error")
                
        with col3:
            st.write(f"{item['size']} MB")
            
        with col4:
            if st.button("Remove", key=f"remove_{item['id']}", help="Remove from queue"):
                st.session_state.batch_queue.remove(item)
                st.experimental_rerun()

def upload_and_process_video():
    """Enhanced upload function with batch processing capabilities."""
    st.subheader("Video Upload")
    
    # Batch vs Single upload toggle
    upload_mode = st.radio("Upload Mode:", ["Single Video", "Batch Upload"], horizontal=True)
    
    if upload_mode == "Single Video":
        # Original single video upload
        video_type = st.selectbox("Select video type:", ["Basic Video (less than 30 mins)", "Podcast (30 mins to 1 hour)"])
        uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "mov", "avi"])

        if uploaded_file and st.button("Process Video", key="process_video_button"):
            # Store processing status
            st.session_state.processing_status[uploaded_file.name] = {
                'status': 'processing',
                'progress': 0,
                'start_time': datetime.now()
            }
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
                tmp_file.write(uploaded_file.read())
                video_path = tmp_file.name
            try:
                with st.spinner("Processing video..."):
                    # Update progress
                    st.session_state.processing_status[uploaded_file.name]['progress'] = 50
                    
                    client = TwelveLabs(api_key=API_KEY)
                    timestamps, video_id = process_video(client, video_path, video_type)
                    
                    # Add to database
                    db.add_video(st.session_state.user_db_id, uploaded_file.name, video_id, 'ready')

                    # Update progress
                    st.session_state.processing_status[uploaded_file.name]['progress'] = 100
                    st.session_state.processing_status[uploaded_file.name]['status'] = 'completed'
                    
                st.success("Video processed successfully!")
                st.session_state.timestamps = timestamps
                st.session_state.video_id = video_id
                st.experimental_rerun()
            except Exception as e:
                display_enhanced_error('processing_error', str(e), get_recovery_suggestions('processing_error'))
                # Update status in DB
                if 'video_id' in locals() and video_id:
                    db.update_video_status(video_id, 'failed')
            finally:
                if 'video_path' in locals() and os.path.exists(video_path):
                    os.remove(video_path)
    
    elif upload_mode == "Batch Upload":
        uploaded_files = st.file_uploader("Choose video files for batch processing", 
                                          type=["mp4", "mov", "avi"], accept_multiple_files=True)
        
        if uploaded_files:
            for file in uploaded_files:
                file_info = {
                    'filename': file.name,
                    'size': round(file.size / (1024 * 1024), 2),
                    'type': file.type
                }
                add_to_batch_queue(file_info)
            
            display_batch_queue()
            
            if st.button("Start Batch Processing", key="start_batch_button"):
                process_batch_queue()
                st.success("Batch processing started. Check the queue for progress.")
                st.experimental_rerun()

                st.session_state.video_id = video_id
                st.session_state.video_url = get_video_url(video_id)
                
                # Store video metadata
                st.session_state.video_metadata[video_id] = {
                    'filename': uploaded_file.name,
                    'upload_time': datetime.now(),
                    'file_size': len(uploaded_file.getvalue()),
                    'video_type': video_type
                }
                
                if st.session_state.video_url:
                    st.video(st.session_state.video_url)
                else:
                    st.info("Video processed successfully! Note: Video streaming is being prepared and may take a few moments to become available.")
                    
            except Exception as e:
                st.session_state.processing_status[uploaded_file.name]['status'] = 'error'
                display_enhanced_error('Upload Error', str(e), get_recovery_suggestions('upload_error'))
            finally:
                os.unlink(video_path)
    
    else:
        # Batch upload mode
        st.write("**Batch Upload Mode** - Upload multiple videos for processing")
        
        uploaded_files = st.file_uploader(
            "Choose video files", 
            type=["mp4", "mov", "avi"],
            accept_multiple_files=True,
            help="Select multiple video files to process in batch"
        )
        
        if uploaded_files:
            st.write(f"Selected {len(uploaded_files)} files:")
            
            total_size = 0
            for file in uploaded_files:
                file_size = len(file.getvalue()) / (1024 * 1024)  # Convert to MB
                total_size += file_size
                st.write(f"   • {file.name} ({file_size:.1f} MB)")
            
            st.write(f"Total size: {total_size:.1f} MB")
            
            col1, col2, col3 = st.columns([1, 1, 1])
            
            with col1:
                if st.button("Add to Queue", key="add_to_queue"):
                    for file in uploaded_files:
                        file_info = {
                            'filename': file.name,
                            'size': len(file.getvalue()) / (1024 * 1024),
                            'type': "Basic Video (less than 30 mins)"  # Default type
                        }
                        add_to_batch_queue(file_info)
                    st.success(f"Added {len(uploaded_files)} files to processing queue!")
                    st.experimental_rerun()
            
            with col2:
                if st.button("Process Queue", key="process_queue", 
                           disabled=st.session_state.batch_processing or not st.session_state.batch_queue):
                    process_batch_queue()
                    st.success("Batch processing completed!")
                    st.experimental_rerun()
            
            with col3:
                if st.button("Clear Queue", key="clear_queue"):
                    st.session_state.batch_queue = []
                    st.session_state.batch_results = {}
                    st.success("Queue cleared!")
                    st.experimental_rerun()
        
        # Display batch queue
        display_batch_queue()
        
        # Display batch results
        if st.session_state.batch_results:
            st.subheader("Batch Results")
            for batch_id, result in st.session_state.batch_results.items():
                with st.expander(f"{result['filename']}"):
                    st.write(f"**Video ID:** {result['video_id']}")
                    st.write("**Timestamps:**")
                    st.code(result['timestamps'])
                    
                    # Quick export for batch results
                    if st.button(f"Copy Timestamps", key=f"copy_batch_{batch_id}"):
                        st.components.v1.html(f"""
                            <script>
                            navigator.clipboard.writeText(`{result['timestamps']}`);
                            </script>
                        """, height=0)
                        st.success("Timestamps copied to clipboard!")

    # Display processing status for persistence
    if st.session_state.processing_status:
        st.subheader("Processing Status")
        for filename, status in st.session_state.processing_status.items():
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                st.write(f"{filename}")
            with col2:
                if status['status'] == 'processing':
                    st.progress(status['progress'] / 100)
                elif status['status'] == 'completed':
                    st.write("Completed")
                elif status['status'] == 'error':
                    st.write("Error")
            with col3:
                if 'start_time' in status:
                    elapsed = datetime.now() - status['start_time']
                    st.write(f"Time: {elapsed.seconds}s")

# Selecting the existing video from the Index and generating timestamps highlight
def select_existing_video():
    try:
        existing_videos = fetch_existing_videos()
        video_options = {f"{video.system_metadata.filename} ({video.id})": video.id for video in existing_videos}
        
        if video_options:
            selected_video = st.selectbox("Select a video:", list(video_options.keys()))
            video_id = video_options[selected_video]
            
            st.session_state.video_id = video_id
            st.session_state.video_url = get_video_url(video_id)
            
            if st.session_state.video_url:
                st.markdown(f"### Selected Video: {selected_video}")
                st.video(st.session_state.video_url)
            else:
                st.markdown(f"### Selected Video: {selected_video}")
                st.info("Note: This video doesn't have a streaming URL available. You can still generate timestamps, but video segments cannot be created.")
            
            if st.button("Generate Timestamps", key="generate_timestamps_button"):
                try:
                    with st.spinner("Generating timestamps..."):
                        client = TwelveLabs(api_key=API_KEY)
                        timestamps, _ = generate_timestamps(client, video_id)
                    st.session_state.timestamps = timestamps
                except ValueError as e:
                    st.error(f"Configuration Error: {str(e)}")
                except Exception as e:
                    st.error(f"Error generating timestamps: {str(e)}")
                    if "api_key" in str(e).lower():
                        st.info("This appears to be an API key issue. Please check your TwelveLabs API configuration.")
        else:
            st.warning("No existing videos found in the index.")
    except Exception as e:
        st.error(str(e))


# Function to display the timestamps and the segments
def display_timestamps_and_segments():
    if st.session_state.timestamps:
        st.subheader("YouTube Chapter Timestamps")
        
        # Enhanced export section
        with st.expander("Export Options", expanded=True):
            st.write("Choose your export format:")
            
            tab1, tab2, tab3 = st.tabs(["YouTube", "JSON", "CSV"])
            
            with tab1:
                create_export_button({
                    'qa_results': st.session_state.qa_results,
                    'chapters': st.session_state.chapters_result,
                    'highlights': st.session_state.highlights_result
                }, export_type="youtube")
            
            with tab2:
                create_export_button({
                    'qa_results': st.session_state.qa_results,
                    'chapters': st.session_state.chapters_result,
                    'highlights': st.session_state.highlights_result
                }, export_type="json")
            
            with tab3:
                create_export_button({
                    'qa_results': st.session_state.qa_results,
                    'chapters': st.session_state.chapters_result,
                    'highlights': st.session_state.highlights_result
                }, export_type="csv")
        
        # Original display
        st.write("**Raw Timestamps:**")
        st.code(st.session_state.timestamps, language="")

        # Check if video URL is available or try to refresh it
        if not st.session_state.video_url and st.session_state.video_id:
            if st.button("Refresh Video URL", key="refresh_video_url_button"):
                try:
                    st.session_state.video_url = get_video_url(st.session_state.video_id)
                    if st.session_state.video_url:
                        st.success("Video URL is now available!")
                        st.experimental_rerun()
                    else:
                        st.info("Video streaming is still being prepared. Please try again in a few moments.")
                except Exception as e:
                    display_enhanced_error('URL Refresh Error', str(e), get_recovery_suggestions('api_error'))

        if st.session_state.video_url:
            if st.button("Create Video Segments", key="create_segments_button"):
                try:
                    process_and_display_segments()
                except Exception as e:
                    display_enhanced_error('Segment Creation Error', str(e), get_recovery_suggestions('processing_error'))
        else:
            st.info("Video segments cannot be created because the video streaming URL is not yet available. This may take a few moments after upload. Try refreshing the video URL above.")

        if st.session_state.video_segments:
            st.subheader("Video Segments")
            for index, (file_name, description) in enumerate(st.session_state.video_segments):
                display_segment(file_name, description, index)

            if st.button("Clear all segments", key="clear_segments_button"):
                for file_name, _ in st.session_state.video_segments:
                    if os.path.exists(file_name):
                        os.remove(file_name)
                st.session_state.video_segments = []
                st.success("All segment files have been cleared.")
                st.experimental_rerun()

def run_app():
    # Configuration status check
    try:
        # Test if we can create a TwelveLabs client
        client = TwelveLabs(api_key=API_KEY)
        st.success("TwelveLabs API configuration is valid!")
    except Exception as e:
        st.error(f"TwelveLabs API configuration error: {str(e)}")
        st.info("""
        **Setup Instructions:**
        1. Copy `.env.example` to `.env`
        2. Get your API key from: https://playground.twelvelabs.io/dashboard/api-key
        3. Create an index at: https://playground.twelvelabs.io/indexes
        4. Add your API_KEY and INDEX_ID to the `.env` file
        5. Restart the application
        """)
        return
    
    # Main navigation tabs
    tab1, tab2, tab3 = st.tabs(["Upload Video", "Select Existing", "Video Q&A"])

    with tab1:
        upload_and_process_video()

    with tab2:
        select_existing_video()

    with tab3:
        display_qa_interface()
    
    # Display timestamps and segments (shown on all tabs when available)
    display_timestamps_and_segments()

def main():
    st.set_page_config(
        page_title="🎬 HootQnA - AI Video Analysis Platform", 
        page_icon="🎬",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Auth0 login
    auth_info = sac.login_button(
        clientId=AUTH0_CLIENT_ID,
        domain=AUTH0_DOMAIN,
    )

    if not auth_info:
        st.warning("Please log in to access the application.")
        st.info("This is a demo application. You can use a dummy email and password to log in if you don't have an account.")
        st.stop()

    st.sidebar.success(f"Welcome, {auth_info['name']}!")
    
    with st.sidebar:
        sac.logout_button()

    run_app()

if __name__ == "__main__":
    main()