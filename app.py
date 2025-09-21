import streamlit as st
import tempfile
import os
from twelvelabs import TwelveLabs

# Try to import utils and handle configuration errors
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
        create_hls_snippet_alternative,
        generate_topics, generate_entities, rewrite_followup_query
    )
except ValueError as e:
    st.error(f"Configuration Error: {str(e)}")
    st.stop()
except Exception as e:
    st.error(f"Error importing utilities: {str(e)}")
    st.stop()

import uuid 

# Set up the Streamlit page configuration
st.set_page_config(page_title="YouTube Chapter Timestamp Generator", layout="wide")

# Custom CSS
st.markdown("""
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://cdn.pixabay.com/photo/2021/08/02/22/41/background-6517956_640.jpg");
    background-size: cover;
}
[data-testid="stHeader"] {
    background-color: rgba(0,0,0,0);
}
[data-testid="stToolbar"] {
    right: 2rem;
    background-image: url("");
    background-size: cover;
}
</style>
""", unsafe_allow_html=True)

# Streamlit Page Header
st.markdown("<h2 style='text-align: center;'>HootQnA: Chat with Videos</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #666;'>Generate timestamps, create video segments, and ask questions about your videos!</p>", unsafe_allow_html=True)
st.markdown("---")

# Initialize session state
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
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []  # list of {role, content}
if 'last_query' not in st.session_state:
    st.session_state.last_query = None
if 'last_search_scope' not in st.session_state:
    st.session_state.last_search_scope = "Current video only"
if 'topics_result' not in st.session_state:
    st.session_state.topics_result = None
if 'entities_result' not in st.session_state:
    st.session_state.entities_result = None


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
                st.session_state.last_query = query
                st.session_state.last_search_scope = search_scope
                # Update chat history (compact)
                st.session_state.chat_history.append({"role": "user", "content": query})
                st.session_state.chat_history.append({"role": "assistant", "content": f"Found {len(search_results)} segments in {('current video' if target_video_id else 'index')} for: {query}"})
                
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
    
    # Conversational follow-up UI
    with st.expander("Ask a follow-up question", expanded=False):
        followup = st.text_input("Follow-up question", key="followup_input", placeholder="e.g., Narrow down to the part about pricing")
        if st.session_state.get('qa_results') and followup and st.button("Ask follow-up", key="followup_button"):
            try:
                client = TwelveLabs(api_key=API_KEY)
                # Keep scope consistent with last search
                scope = st.session_state.get('last_search_scope', search_scope)
                target_video_id = st.session_state.video_id if scope == "Current video only" else None
                # Rewrite follow-up to standalone
                rewritten = rewrite_followup_query(client, target_video_id, st.session_state.chat_history, followup)
                standalone_query = rewritten.get('query') or followup
                with st.spinner("Searching follow-up..."):
                    results = search_video_content(client, target_video_id, standalone_query, max_results)
                if not results:
                    st.info(f"No results for follow-up: '{standalone_query}'")
                else:
                    st.session_state.qa_results = results
                    st.session_state.last_query = standalone_query
                    st.session_state.chat_history.append({"role": "user", "content": followup})
                    st.session_state.chat_history.append({"role": "assistant", "content": f"Rewritten: {standalone_query}. Found {len(results)} segments."})
                    # Render results in the same selected analysis mode
                    if analysis_mode == "With Video Summary":
                        formatted_results = format_qa_results_with_summary(results, standalone_query, client)
                    elif analysis_mode == "Enhanced Analysis":
                        formatted_results = format_qa_results(results, standalone_query, client, include_rich_analysis=True)
                    else:
                        formatted_results = format_qa_results(results, standalone_query, client, include_rich_analysis=False)
                    st.markdown(formatted_results)
            except Exception as e:
                st.error(f"Follow-up error: {str(e)}")
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
            try:
                with st.spinner("Generating video summary..."):
                    client = TwelveLabs(api_key=API_KEY)
                    summary_result = generate_summary(client, st.session_state.video_id)

                    st.subheader("Video Summary")
                    st.write(summary_result['summary'])

            except Exception as e:
                st.error(f"Error generating summary: {str(e)}")

    with col2:
        if st.button("Generate Chapters", key="gen_chapters_btn"):
            try:
                with st.spinner("Generating video chapters and creating snippets..."):
                    client = TwelveLabs(api_key=API_KEY)
                    chapters_result = generate_chapters(client, st.session_state.video_id)

                    st.subheader("Video Chapters with Snippets")

                    # Store chapters result in session state
                    st.session_state.chapters_result = chapters_result
                    st.session_state.chapter_snippets = []

                    # Auto-create all snippets and display them
                    for chapter in chapters_result['chapters']:
                        start_time = seconds_to_mmss(chapter['start_sec'])
                        end_time = seconds_to_mmss(chapter['end_sec'])
                        duration = chapter['end_sec'] - chapter['start_sec']

                        st.markdown(f"### Chapter {chapter['chapter_number']}: {chapter['chapter_title']}")
                        st.write(f"**Time:** {start_time} - {end_time} ({duration:.1f}s)")
                        st.write(f"**Summary:** {chapter['chapter_summary']}")

                        # Try to create snippet automatically
                        snippet_created = False
                        snippet_filename = None

                        if st.session_state.video_url and st.session_state.video_id:
                            try:
                                # Try using HLS-compatible method first
                                try:
                                    snippet_filename = create_hls_snippet_alternative(
                                        video_id=st.session_state.video_id,
                                        start_time=chapter['start_sec'],
                                        end_time=chapter['end_sec'],
                                        title=chapter['chapter_title'],
                                        snippet_type="chapter"
                                    )
                                    snippet_created = True
                                except Exception:
                                    # Fallback to URL-based method
                                    snippet_filename = create_analysis_video_snippet(
                                        video_url=st.session_state.video_url,
                                        start_time=chapter['start_sec'],
                                        end_time=chapter['end_sec'],
                                        title=chapter['chapter_title'],
                                        snippet_type="chapter"
                                    )
                                    snippet_created = True

                                # Store snippet info
                                st.session_state.chapter_snippets.append({
                                    'filename': snippet_filename,
                                    'title': chapter['chapter_title'],
                                    'chapter_number': chapter['chapter_number']
                                })

                            except Exception as e:
                                st.warning(f"Could not create snippet: {str(e)}")

                        # Display snippet or placeholder
                        col_video, col_download = st.columns([2, 1])

                        with col_video:
                            if snippet_created and os.path.exists(snippet_filename):
                                st.video(snippet_filename)
                                st.success("Snippet ready!")
                            else:
                                # Show placeholder or HLS stream if available
                                if st.session_state.video_url:
                                    st.info(f"Video segment: {start_time} - {end_time}")
                                    # Try to show the main video with timestamp info
                                    try:
                                        video_html = get_hls_player_html(st.session_state.video_url)
                                        st.components.v1.html(video_html, height=300)
                                        st.caption(f"Jump to {start_time} in the main video")
                                    except Exception:
                                        st.warning("Video preview not available")
                                else:
                                    st.info("Snippet creation requires video URL")

                        with col_download:
                            if snippet_created and os.path.exists(snippet_filename):
                                with open(snippet_filename, "rb") as file:
                                    file_contents = file.read()
                                st.download_button(
                                    label="Download",
                                    data=file_contents,
                                    file_name=snippet_filename,
                                    mime="video/mp4",
                                    key=f"download_chapter_{chapter['chapter_number']}",
                                    help=f"Download Chapter {chapter['chapter_number']} snippet"
                                )
                            else:
                                st.button(
                                    "Retry Snippet",
                                    key=f"retry_chapter_{chapter['chapter_number']}",
                                    help="Try creating snippet again",
                                    disabled=not st.session_state.video_url
                                )

                        st.markdown("---")

            except Exception as e:
                st.error(f"Error generating chapters: {str(e)}")

    with col3:
        if st.button("Generate Highlights", key="gen_highlights_btn"):
            try:
                with st.spinner("Generating video highlights and creating snippets..."):
                    client = TwelveLabs(api_key=API_KEY)
                    highlights_result = generate_highlights(client, st.session_state.video_id)

                    st.subheader("Video Highlights with Snippets")

                    # Store highlights result in session state
                    st.session_state.highlights_result = highlights_result
                    st.session_state.highlight_snippets = []

                    # Auto-create all snippets and display them
                    for i, highlight in enumerate(highlights_result['highlights'], 1):
                        start_time = seconds_to_mmss(highlight['start_sec'])
                        end_time = seconds_to_mmss(highlight['end_sec'])
                        duration = highlight['end_sec'] - highlight['start_sec']

                        st.markdown(f"### Highlight {i}: {highlight['highlight']}")
                        st.write(f"**Time:** {start_time} - {end_time} ({duration:.1f}s)")
                        if highlight.get('highlight_summary'):
                            st.write(f"**Details:** {highlight['highlight_summary']}")

                        # Try to create snippet automatically
                        snippet_created = False
                        snippet_filename = None

                        if st.session_state.video_url and st.session_state.video_id:
                            try:
                                # Try using HLS-compatible method first
                                try:
                                    snippet_filename = create_hls_snippet_alternative(
                                        video_id=st.session_state.video_id,
                                        start_time=highlight['start_sec'],
                                        end_time=highlight['end_sec'],
                                        title=highlight['highlight'],
                                        snippet_type="highlight"
                                    )
                                    snippet_created = True
                                except Exception:
                                    # Fallback to URL-based method
                                    snippet_filename = create_analysis_video_snippet(
                                        video_url=st.session_state.video_url,
                                        start_time=highlight['start_sec'],
                                        end_time=highlight['end_sec'],
                                        title=highlight['highlight'],
                                        snippet_type="highlight"
                                    )
                                    snippet_created = True

                                # Store snippet info
                                st.session_state.highlight_snippets.append({
                                    'filename': snippet_filename,
                                    'title': highlight['highlight'],
                                    'highlight_number': i
                                })

                            except Exception as e:
                                st.warning(f"Could not create snippet: {str(e)}")

                        # Display snippet or placeholder
                        col_video, col_download = st.columns([2, 1])

                        with col_video:
                            if snippet_created and os.path.exists(snippet_filename):
                                st.video(snippet_filename)
                                st.success("Snippet ready!")
                            else:
                                # Show placeholder or HLS stream if available
                                if st.session_state.video_url:
                                    st.info(f"Video segment: {start_time} - {end_time}")
                                    # Try to show the main video with timestamp info
                                    try:
                                        video_html = get_hls_player_html(st.session_state.video_url)
                                        st.components.v1.html(video_html, height=300)
                                        st.caption(f"Jump to {start_time} in the main video")
                                    except Exception:
                                        st.warning("Video preview not available")
                                else:
                                    st.info("Snippet creation requires video URL")

                        with col_download:
                            if snippet_created and os.path.exists(snippet_filename):
                                with open(snippet_filename, "rb") as file:
                                    file_contents = file.read()
                                st.download_button(
                                    label="Download",
                                    data=file_contents,
                                    file_name=snippet_filename,
                                    mime="video/mp4",
                                    key=f"download_highlight_{i}",
                                    help=f"Download Highlight {i} snippet"
                                )
                            else:
                                st.button(
                                    "Retry Snippet",
                                    key=f"retry_highlight_{i}",
                                    help="Try creating snippet again",
                                    disabled=not st.session_state.video_url
                                )

                        st.markdown("---")

            except Exception as e:
                st.error(f"Error generating highlights: {str(e)}")

    # Additional advanced insights: Topics and Entities
    st.markdown("---")
    st.subheader("Advanced Insights")
    col_t1, col_t2 = st.columns([1, 1])
    with col_t1:
        if st.button("Generate Topics", key="gen_topics_btn"):
            try:
                with st.spinner("Extracting topics..."):
                    client = TwelveLabs(api_key=API_KEY)
                    st.session_state.topics_result = generate_topics(client, st.session_state.video_id)
            except Exception as e:
                st.error(f"Error extracting topics: {str(e)}")
    with col_t2:
        if st.button("Extract Entities", key="gen_entities_btn"):
            try:
                with st.spinner("Extracting entities..."):
                    client = TwelveLabs(api_key=API_KEY)
                    st.session_state.entities_result = generate_entities(client, st.session_state.video_id)
            except Exception as e:
                st.error(f"Error extracting entities: {str(e)}")

    # Render Topics
    if st.session_state.topics_result:
        topics = st.session_state.topics_result.get('topics', [])
        if topics:
            st.markdown("### Topics")
            for t in topics:
                start = seconds_to_mmss(t.get('first_sec', 0))
                end = seconds_to_mmss(t.get('last_sec', 0))
                sal = f"{t.get('salience', 0)*100:.0f}%"
                st.write(f"- **{t.get('name')}** (salience: {sal}) — {start} to {end}; keywords: {', '.join(t.get('keywords', []))}")
        else:
            st.info("No topics detected.")

    # Render Entities grouped by type
    if st.session_state.entities_result:
        entities = st.session_state.entities_result.get('entities', [])
        if entities:
            st.markdown("### Entities")
            by_type = {}
            for e in entities:
                by_type.setdefault(e.get('type', 'other'), []).append(e)
            for typ, arr in by_type.items():
                st.write(f"**{typ.title()}** ({len(arr)}):")
                for e in arr[:10]:  # show up to 10 per type
                    start = seconds_to_mmss(e.get('first_sec', 0))
                    end = seconds_to_mmss(e.get('last_sec', 0))
                    conf = f"{e.get('confidence', 0)*100:.0f}%"
                    st.write(f"- {e.get('name')} (conf: {conf}, mentions: {e.get('mentions', 0)}) — {start} to {end}")
        else:
            st.info("No entities detected.")

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
            try:
                with st.spinner("Performing custom analysis..."):
                    client = TwelveLabs(api_key=API_KEY)
                    analysis_result = generate_open_analysis(
                        client,
                        st.session_state.video_id,
                        custom_prompt,
                        temperature=0.3
                    )

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
def upload_and_process_video():
    video_type = st.selectbox("Select video type:", ["Basic Video (less than 30 mins)", "Podcast (30 mins to 1 hour)"])
    uploaded_file = st.file_uploader("Choose a video file", type=["mp4", "mov", "avi"])

    if uploaded_file and st.button("Process Video", key="process_video_button"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
            tmp_file.write(uploaded_file.read())
            video_path = tmp_file.name
        try:
            with st.spinner("Processing video..."):
                client = TwelveLabs(api_key=API_KEY)
                timestamps, video_id = process_video(client, video_path, video_type)
            st.success("Video processed successfully!")
            st.session_state.timestamps = timestamps
            st.session_state.video_id = video_id
            st.session_state.video_url = get_video_url(video_id)
            if st.session_state.video_url:
                st.video(st.session_state.video_url)
            else:
                st.info("Video processed successfully! Note: Video streaming is being prepared and may take a few moments to become available.")
        except ValueError as e:
            st.error(f"Configuration Error: {str(e)}")
        except Exception as e:
            st.error(f"Processing Error: {str(e)}")
            if "api_key" in str(e).lower():
                st.info("This appears to be an API key issue. Please check your TwelveLabs API configuration.")
        finally:
            os.unlink(video_path)

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
        st.write("Copy the Timestamp description and add it to the Youtube Video Description")
        st.code(st.session_state.timestamps, language="")

        # Check if video URL is available or try to refresh it
        if not st.session_state.video_url and st.session_state.video_id:
            if st.button("Refresh Video URL", key="refresh_video_url_button"):
                st.session_state.video_url = get_video_url(st.session_state.video_id)
                if st.session_state.video_url:
                    st.success("Video URL is now available!")
                    st.experimental_rerun()
                else:
                    st.info("Video streaming is still being prepared. Please try again in a few moments.")

        if st.session_state.video_url:
            if st.button("Create Video Segments", key="create_segments_button"):
                try:
                    process_and_display_segments()
                except Exception as e:
                    st.error(f"Error creating video segments: {str(e)}")
                    st.exception(e)  # This will display the full traceback
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

def main():
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
    tab1, tab2, tab3 = st.tabs(["**Upload Video**", "**Select Existing**", "**Video Q&A**"])

    with tab1:
        upload_and_process_video()

    with tab2:
        select_existing_video()

    with tab3:
        display_qa_interface()
    
    # Display timestamps and segments (shown on all tabs when available)
    display_timestamps_and_segments()

if __name__ == "__main__":
    main()