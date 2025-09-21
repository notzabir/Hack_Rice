@echo off
echo 🤖 Starting Discord Bot Server for TwelveLabs Study Guide...
echo.
echo 📋 Pre-flight checks:
echo ✅ Make sure your .env file has DISCORD_BOT_TOKEN and DISCORD_CHANNEL_ID
echo ✅ Make sure you've installed: pip install fastapi uvicorn discord.py python-multipart
echo.
echo 🚀 Starting server on http://localhost:8000
echo 📖 Visit http://localhost:8000 for status
echo 🛑 Press Ctrl+C to stop
echo.

python discord_bot_server.py