# HootHive — Lecture Summarizer, Chapter Notes & Video Q&A

Upload and manage your lecture recordings with AI-powered chapter generation, study notes, and Q&A — powered by **TwelveLabs AI**.  

## 📌 About

**HootHive** is an AI-powered learning assistant designed for students.  
Instead of relying on YouTube links, students can **upload their own lecture recordings (in bulk)**, and HootHive will automatically:  

- Generate **chapter timestamps** for each lecture  
- Create **summaries and structured notes**  
- Build **study packs** (flashcards, quizzes, and PDFs)  
- Provide a **Q&A interface** to quickly find relevant lecture segments  
- Share lecture notes, timestamps, and PDFs directly in Discord with **HootBot**  

Perfect for students who need to manage a **large library of lectures**, HootHive turns raw video files into **organized, searchable, and shareable study material**.  

---

## ✨ Key Features

### 🎬 Core Lecture Processing
- **Bulk Lecture Uploads**: Upload multiple lecture files at once (MP4, MOV, MKV, etc.)  
- **Automatic Chapter Generation**: AI detects logical breaks (topics, sections) in each lecture  
- **Lecture Management Dashboard**: View, search, and organize all uploaded lectures  
- **Video Segmentation**: Export specific sections as downloadable clips  

### 📚 Learning & Study Material Creation
- **Lecture Summaries**: Short, medium, and detailed summaries for each lecture  
- **Chapterwise Notes**: Auto-generated notes per topic/section  
- **Highlight Extraction**: Capture the most important insights and examples  
- **Study Pack Builder**:
  - Flashcards (Q/A style)  
  - Quizzes (MCQs and short-answer)  
  - Topic-based study guides  
- **PDF Export**: Bundle notes, summaries, flashcards, and quizzes into downloadable PDFs  

### 🤖 Lecture Q&A Explorer
- **Natural Language Questions**: e.g., *“Where does the professor explain recursion?”*  
- **Relevant Segment Retrieval**: Exact timestamps and snippets returned from your lectures  
- **Confidence Scoring**: Results ranked by accuracy (0–100%)  
- **Auto-Snippets**: Convert retrieved lecture parts into mini-clips  
- **Multi-modal Search**: Works across audio (speech), visuals (slides), and transcripts  

### 🐦 Discord Collaboration (HootBot)
- **HootBot Integration**: Connects HootHive with your study group’s Discord server  
- **Lecture Sharing**: Post summaries, PDFs, and flashcards directly to a channel  
- **Group Study Mode**: Collaborate on shared notes and highlight important parts together  
- **Slash Commands**: e.g., `/hoothive search <lecture> <query>` to quickly retrieve answers  

### ⚡ Real-time Features
- **Bulk Processing Queue**: Upload multiple lectures and track their status  
- **Live Progress Bars**: See upload and analysis progress for each lecture  
- **Instant Q&A**: Low-latency answers to your questions  

---

## 🛠️ Tech Stack

- **Frontend**: Streamlit  
- **AI / Multimodal**: TwelveLabs AI Platform  
- **Video Processing**: MoviePy  
- **Backend**: Python (FastAPI optional for batch APIs)  
- **Config**: dotenv for environment variables  
- **Integrations**: Discord.py (HootBot), MongoDB Atlas (lecture metadata & indexing), AWS/GCP storage  

---

## 🚀 Quick Setup

### 1. Prerequisites
- Python 3.8+  
- TwelveLabs account + API key  
- Git  
- (Optional) Discord bot token for HootBot  
- (Optional) MongoDB Atlas for persistent lecture storage  

### 2. Installation
``
# Clone repository
git clone https://github.com/notzabir/Hack_Rice.git

cd HootHive-Lecture-QA

# Install dependencies
pip install -r requirements.txt

HootHive Demo -

https://www.youtube.com/watch?v=aJLemxw8aEg

## Features

🎯 **Chapter Generation**: Automatically detect and create timestamps with highlights for video chapters.

🔍 **Content Segmentation**: Identify key points in the video based on its content.

🚀 **Streamlined Navigation**: Enhance the viewing experience with clickable chapters for easier navigation.

## Tech Stack

- **Frontend**: Streamlit
- **Backend**: Python
- **Deployment**: Streamlit Cloud

## Instructions on running project locally

To run HootHive locally, follow these steps -

### Step 1 - Clone the project

```bash
git clone https://github.com/notzabir/Hack_Rice.git
```

Step 2 -

Install dependencies:

```bash
 cd Hack_Rice

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




## License

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
