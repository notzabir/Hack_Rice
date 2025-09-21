# Video Q&A Interface Usage Guide

## 🤖 What is the Video Q&A Interface?

The Video Q&A interface allows you to ask questions about your uploaded videos and automatically retrieve relevant video segments as answers. This feature uses TwelveLabs AI to understand your video content and find the most relevant portions.

## 🎯 How to Use the Q&A Interface

### Step 1: Prepare Your Video

1. **Upload a new video** or **select an existing video** from the first two tabs
2. Wait for the video to be processed (you'll see "Video processed successfully!")
3. Navigate to the **"🤖 Video Q&A"** tab

### Step 2: Ask Questions

1. **Enter your question** in the search box. Examples:

   - "What are the main topics discussed?"
   - "Show me the introduction"
   - "Where is the conclusion?"
   - "What products are mentioned?"
   - "Find sections about pricing"
   - "Show me when they talk about features"

2. **Select max results** (3, 5, or 10 segments)

3. **Click "Search Video"** to find relevant segments

### Step 3: Review Results

The interface will show:

- **Confidence Score**: How relevant each segment is (higher = more relevant)
- **Timestamps**: Start and end time of each segment
- **Duration**: Length of each segment
- **Content Preview**: Text preview of what's discussed in that segment

### Step 4: Create Video Snippets

1. **Click "Create Video Snippets"** to generate downloadable video clips
2. Wait for processing (progress bar will show status)
3. **Download individual snippets** or view them inline

## 🔍 Types of Questions You Can Ask

### Content-Based Questions

- "What topics are covered?"
- "Where do they discuss [specific topic]?"
- "Show me the main points"

### Structure-Based Questions

- "Find the introduction"
- "Where is the conclusion?"
- "Show me the summary section"

### Object/Person Recognition

- "When do people appear on screen?"
- "Show me product demonstrations"
- "Find slides or presentations"

### Keyword-Based Searches

- "Find mentions of [specific word/phrase]"
- "Where do they talk about pricing?"
- "Show segments about features"

## 📊 Understanding Results

### Confidence Scores

- **90-100%**: Extremely relevant match
- **70-90%**: Highly relevant match
- **50-70%**: Moderately relevant match
- **Below 50%**: Low relevance (may still be useful)

### Time Segments

- Results show exact timestamps you can reference
- Segments are automatically trimmed to relevant portions
- Duration shows how long each segment is

## 🎬 Video Snippet Features

### Automatic Naming

- Snippets are named based on your query and timestamps
- Format: `qa_snippet_01_your_query_00:30-01:45.mp4`

### Download Options

- Each snippet can be downloaded individually
- MP4 format compatible with most players
- Includes metadata about confidence and timing

## 💡 Tips for Better Results

### Write Clear Questions

- ✅ "Where do they explain the installation process?"
- ❌ "installation"

### Be Specific

- ✅ "Show me product pricing information"
- ❌ "money stuff"

### Use Natural Language

- ✅ "What are the main benefits discussed?"
- ❌ "benefits main what"

### Try Different Phrasings

- If you don't get good results, try rephrasing your question
- Use synonyms or different terms

## ⚡ Troubleshooting

### "Video is still being processed"

- Wait a few minutes after upload
- Video needs to be fully indexed for search

### "No relevant segments found"

- Try rephrasing your question
- Use broader or more specific terms
- Check if the content actually exists in the video

### "Video snippets require streaming URL"

- Click "Refresh Video URL" in the timestamps section
- Some videos may not support streaming immediately

### Poor Search Results

- Ensure your question relates to actual video content
- Try shorter, more focused queries
- Use specific keywords that appear in the video

## 🔧 Technical Requirements

- Video must be fully processed and indexed
- Streaming URL must be available for snippet creation
- TwelveLabs index must support search capabilities
- Video should have clear audio/visual content for best results

## 📈 Advanced Usage

### Combining with Timestamps

- Use Q&A to find specific sections
- Use timestamp generator for overall chapter structure
- Create focused segments with Q&A, full chapters with timestamps

### Multiple Queries

- Ask several questions to explore different aspects
- Each query creates separate snippets
- Results are ordered by relevance

### Content Analysis

- Use Q&A to analyze video content themes
- Identify key discussion points
- Extract specific information or quotes
