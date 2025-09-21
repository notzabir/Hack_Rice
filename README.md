# YouTube Chapter Highlight Generator & Video Q&A

Generate chapter highlight timestamps and ask questions about your YouTube videos using TwelveLabs AI.

## About

The YouTube Chapter Highlight Generator is an AI-powered tool that automatically generates chapter timestamps for YouTube videos and provides an intelligent Q&A interface for video content exploration. By analyzing video content using TwelveLabs AI, it identifies key segments, creates timestamps, and allows you to ask questions to retrieve specific video portions.

This tool helps content creators save time and effort by automatically generating timestamp highlights and providing instant access to specific video content through natural language queries.

## Features

### 📹 Core Video Processing

- **Video Upload & Processing**: Upload videos and process them using TwelveLabs AI
- **Automatic Chapter Generation**: AI-powered analysis to identify key video segments
- **YouTube-Ready Timestamps**: Generate formatted timestamps for YouTube descriptions
- **Video Segmentation**: Create downloadable video segments based on chapters
- **Existing Video Management**: Browse and select from previously uploaded videos

### 🤖 Video Q&A Interface

- **Natural Language Queries**: Ask questions about your video in plain English
- **Intelligent Content Search**: Find relevant video segments based on your queries
- **Confidence Scoring**: See how relevant each result is to your question
- **Smart Video Snippets**: Automatically create video clips for relevant segments
- **Multi-modal Search**: Search across visual content, conversations, and text

### ⚡ Real-time Features

- **Live Processing Updates**: Real-time status of video processing
- **Instant Search Results**: Quick response to Q&A queries
- **Progress Tracking**: Visual progress bars for all operations

## Tech Stack

- **Frontend**: Streamlit
- **AI/ML**: TwelveLabs AI Platform
- **Video Processing**: MoviePy
- **Backend**: Python
- **Environment**: dotenv for configuration

## Quick Setup

### 1. Prerequisites

- Python 3.8 or higher
- TwelveLabs account and API key
- Git

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/Hrishikesh332/Twelvelabs-Youtube-Chapter-Timestamp.git
cd Twelvelabs-Youtube-Chapter-Timestamp

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

1. **Get TwelveLabs Credentials**:

   - Sign up at [TwelveLabs Platform](https://playground.twelvelabs.io/)
   - Get your API key from the dashboard
   - Create an index and note the Index ID

2. **Create Environment File**:

   ```bash
   # Copy the example file
   cp .env.example .env

   # Edit the .env file with your credentials
   ```

3. **Add Your Credentials to `.env`**:
   ```env
   TWELVE_LABS_API_KEY=your_api_key_here
   TWELVE_LABS_INDEX_ID=your_index_id_here
   ```

### 4. Test Configuration

```bash
# Run the configuration test
python test_config.py
```

This will verify your API credentials and connection.

### 5. Launch Application

```bash
# Start the Streamlit app
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`.

## Usage

### 📤 Uploading New Videos

1. **Upload Video**: Use the file uploader to select your video file
2. **Processing**: Wait for the video to be uploaded and processed by TwelveLabs
3. **Generate Timestamps**: The AI will automatically analyze the video and generate chapter timestamps
4. **Copy Timestamps**: Copy the generated timestamps and paste them into your YouTube video description
5. **Create Segments** (Optional): Generate downloadable video segments for each chapter

### 📂 Using Existing Videos

1. **Select from Existing**: Choose "Select from existing videos" option
2. **Browse Videos**: Select from your previously uploaded videos
3. **Generate Timestamps**: Generate new timestamps or view existing ones
4. **Create Segments**: Generate video segments if streaming is available

### 🤖 Video Q&A Interface

The new Q&A interface allows you to ask questions about your videos and get relevant video segments as answers!

#### How to Use Q&A:

1. **Navigate to Q&A Tab**: Click on "🤖 Video Q&A" after uploading/selecting a video
2. **Ask Questions**: Type natural language questions like:
   - "What are the main topics discussed?"
   - "Show me the introduction"
   - "Where do they talk about pricing?"
   - "Find the conclusion section"
3. **Get Results**: View relevant segments with confidence scores and timestamps
4. **Create Snippets**: Generate downloadable video clips for the most relevant parts

#### Example Queries:

- **Content Discovery**: "What products are mentioned?"
- **Section Finding**: "Show me the tutorial section"
- **Topic Search**: "Find discussions about features"
- **Structure Navigation**: "Where is the summary?"

#### Q&A Features:

- 🎯 **Confidence Scoring**: See how relevant each result is (0-100%)
- ⏰ **Precise Timestamps**: Exact start/end times for each segment
- 📹 **Auto-Snippet Creation**: Generate video clips from search results
- 💬 **Content Preview**: See text content from each segment
- 🔍 **Multi-modal Search**: Searches visual, audio, and text content

For detailed Q&A usage instructions, see [QA_USAGE_GUIDE.md](QA_USAGE_GUIDE.md).

## Troubleshooting

### Common Issues

**"The client must be instantiated by either passing in api_key or setting TWELVE_LABS_API_KEY"**

- Solution: Ensure your `.env` file contains the correct `TWELVE_LABS_API_KEY`

**"Failed to get video URL: 404 Not Found"**

- Solution: Wait a few moments after upload for video streaming to be ready, then click "Refresh Video URL"

**"Video streaming is not available"**

- Solution: This is normal for some videos. You can still use the timestamps, but video segmentation won't be available

**Configuration test fails**

- Solution: Verify your API key and Index ID are correct in the `.env` file

### Getting Help

1. Run `python test_config.py` to diagnose configuration issues
2. Check the [TwelveLabs Documentation](https://docs.twelvelabs.io/)
3. Ensure your TwelveLabs index supports video streaming if you need segment creation

## API Requirements

- **TwelveLabs SDK**: Version 1.0.2 or higher
- **Python**: 3.8+
- **Index Type**: Multimodal index with video analysis capabilities

For the most up-to-date setup instructions, visit the [TwelveLabs Documentation](https://docs.twelvelabs.io/).
border: none;
border-radius: 8px;
text-align: center;
text-decoration: none;
box-shadow: 0 4px 8px rgba(0,0,0,0.2);
transition: background-color 0.3s, box-shadow 0.3s;
">
YouTube Chapter Timestamp App
</a>

Demo and Video Explanation -

[![Watch the video](https://img.youtube.com/vi/z-_PJqjTZmM/hqdefault.jpg)](https://youtu.be/z-_PJqjTZmM)

## Features

🎯 **Chapter Generation**: Automatically detect and create timestamps with highlights for video chapters.

🔍 **Content Segmentation**: Identify key points in the video based on its content.

🚀 **Streamlined Navigation**: Enhance the viewing experience with clickable chapters for easier navigation.

## Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python
- **Deployment**: Streamlit Cloud

## Instructions on running project locally

To run the YouTube Chapter Highlight Generator locally, follow these steps -

### Step 1 - Clone the project

```bash
git clone https://github.com/Hrishikesh332/Twelvelabs-Youtube-Chapter-Timestamp.git
```

Step 2 -

Install dependencies:

```bash
 cd Youtube-Chapter-Timestamp-App

 pip install -r requirements.txt
```

Step 3 -

Set up your Twelve Labs account -

Create an account on the Twelve Labs Portal
Navigate to the Twelve Labs Playground
Create a new index, select Marengo 2.6 and Pegasus 1.1

Step 4 -

Get your API Key from the [Twelve Labs Dashboard](https://playground.twelvelabs.io/dashboard/api-key)
Find your INDEX_ID in the URL of your created [index](https://playground.twelvelabs.io/indexes/{index_id})

Step 5 -

Configure the application with your API credentials:

1. Copy the `.env.example` file to `.env`:

```bash
cp .env.example .env
```

2. Edit the `.env` file and add your credentials:

```env
API_KEY=your_twelvelabs_api_key_here
INDEX_ID=your_index_id_here
```

**Important**: Never commit your `.env` file to version control. It's already included in `.gitignore`.

Step 6 -

Run the Streamlit application

```bash
  streamlit run app.py
```

Step 7 -

Access the application at:

```bash
  http://localhost:8501/
```

## Usecases

📽️**YouTube Content Creators**: Automatically generate chapter highlight markers for improved video navigation.

🎓 **Educational Videos**: Make it easier for students to jump to specific sections of long tutorial videos.

🎥 **Content Review**: Easily navigate to important points in long-form video content.

## Feedback

If you have any feedback, please reach out to us at **hriskikesh.yadav332@gmail.com**

## License

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
