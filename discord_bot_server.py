#!/usr/bin/env python3
"""
Discord Bot Server for Study Guide PDF Sharing
Receives PDF files from Streamlit app and sends them to Discord channel
"""

import os
import asyncio
import logging
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import discord
from discord.ext import commands
import uvicorn
from dotenv import load_dotenv
import tempfile
from pathlib import Path

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Discord bot configuration
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID")) if os.getenv("DISCORD_CHANNEL_ID") else None
SERVER_PORT = int(os.getenv("DISCORD_SERVER_PORT", 8000))

# Validate configuration
if not DISCORD_BOT_TOKEN or DISCORD_BOT_TOKEN == "your_discord_bot_token_here":
    raise ValueError("DISCORD_BOT_TOKEN not configured in .env file")

if not DISCORD_CHANNEL_ID:
    raise ValueError("DISCORD_CHANNEL_ID not configured in .env file")

# Initialize FastAPI app
app = FastAPI(
    title="Discord Bot Server",
    description="Receives PDF files and sends them to Discord channel",
    version="1.0.0"
)

# Initialize Discord bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Global variables to track bot status
bot_ready = False
target_channel = None

@bot.event
async def on_ready():
    """Called when the bot is ready and connected to Discord"""
    global bot_ready, target_channel
    
    logger.info(f'{bot.user} has connected to Discord!')
    
    # Get the target channel
    target_channel = bot.get_channel(DISCORD_CHANNEL_ID)
    if target_channel:
        logger.info(f'Target channel found: {target_channel.name}')
        bot_ready = True
    else:
        logger.error(f'Channel with ID {DISCORD_CHANNEL_ID} not found!')
        bot_ready = False

@bot.event
async def on_error(event, *args, **kwargs):
    """Handle bot errors"""
    logger.error(f'Discord bot error in event {event}: {args}')

# FastAPI Routes

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Discord Bot Server is running",
        "bot_status": "online" if bot_ready else "offline",
        "channel_id": DISCORD_CHANNEL_ID
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for external monitoring"""
    return {
        "status": "healthy",
        "bot_online": bot_ready,
        "bot_user": str(bot.user) if bot.user else None,
        "channel_connected": target_channel is not None,
        "message": "Bot is ready" if bot_ready else "Bot is starting"
    }

@app.get("/status")
async def get_status():
    """Get detailed bot status"""
    return {
        "online": bot_ready,
        "bot_user": str(bot.user) if bot.user else None,
        "channel_id": DISCORD_CHANNEL_ID,
        "channel_name": target_channel.name if target_channel else None,
        "message": "Bot is online and ready" if bot_ready else "Bot is starting up or offline"
    }

@app.post("/send_pdf")
async def send_pdf_to_discord(file: UploadFile = File(...)):
    """
    Receive PDF file and send it to Discord channel
    """
    try:
        if not bot_ready:
            raise HTTPException(
                status_code=503,
                detail="Discord bot is not ready. Please wait a moment and try again."
            )
        
        if not target_channel:
            raise HTTPException(
                status_code=404,
                detail=f"Discord channel with ID {DISCORD_CHANNEL_ID} not found"
            )
        
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed"
            )
        
        # Read file content
        content = await file.read()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Create Discord file object
            discord_file = discord.File(tmp_file_path, filename=file.filename)
            
            # Send to Discord channel
            message = await target_channel.send(
                content="📄 **Study Guide PDF** uploaded from TwelveLabs Video Analyzer!",
                file=discord_file
            )
            
            logger.info(f"Successfully sent PDF {file.filename} to Discord channel {target_channel.name}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "success": True,
                    "message": f"PDF successfully sent to #{target_channel.name}",
                    "discord_message_id": message.id,
                    "filename": file.filename,
                    "file_size": len(content)
                }
            )
            
        finally:
            # Clean up temporary file
            try:
                os.unlink(tmp_file_path)
            except OSError:
                pass
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending PDF to Discord: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send PDF to Discord: {str(e)}"
        )

@app.post("/test-connection")
async def test_discord_connection():
    """Test Discord connection and send a test message"""
    try:
        if not bot_ready or not target_channel:
            raise HTTPException(
                status_code=503,
                detail="Discord bot is not ready"
            )
        
        # Send test message
        message = await target_channel.send("🤖 Discord bot connection test successful!")
        
        return {
            "success": True,
            "message": "Test message sent successfully",
            "channel": target_channel.name,
            "message_id": message.id
        }
        
    except Exception as e:
        logger.error(f"Test connection failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Test connection failed: {str(e)}"
        )

# Discord bot commands (optional)
@bot.command(name='ping')
async def ping(ctx):
    """Simple ping command"""
    await ctx.send('🏓 Pong! Bot is online and ready to receive PDFs!')

@bot.command(name='status')
async def status_command(ctx):
    """Check bot status"""
    embed = discord.Embed(
        title="📊 Bot Status",
        description="TwelveLabs Study Guide PDF Bot",
        color=0x00ff00
    )
    embed.add_field(name="Status", value="🟢 Online", inline=True)
    embed.add_field(name="Channel", value=f"#{target_channel.name}", inline=True)
    embed.add_field(name="Ready to receive", value="📄 PDF files", inline=True)
    
    await ctx.send(embed=embed)

# Background task to run Discord bot
async def start_discord_bot():
    """Start the Discord bot in the background"""
    try:
        await bot.start(DISCORD_BOT_TOKEN)
    except Exception as e:
        logger.error(f"Failed to start Discord bot: {str(e)}")

# Startup event
@app.on_event("startup")
async def startup_event():
    """Start Discord bot when FastAPI starts"""
    logger.info("Starting Discord bot...")
    asyncio.create_task(start_discord_bot())

# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    logger.info("Shutting down Discord bot...")
    if bot:
        await bot.close()

if __name__ == "__main__":
    print("🤖 Starting Discord Bot Server...")
    print(f"📡 Server will run on http://localhost:{SERVER_PORT}")
    print(f"🎯 Target Discord Channel ID: {DISCORD_CHANNEL_ID}")
    print(f"🔑 Bot Token: {'✅ Configured' if DISCORD_BOT_TOKEN else '❌ Missing'}")
    print("\n⚡ Starting server...")
    
    # Run the FastAPI server
    uvicorn.run(
        "discord_bot_server:app",
        host="0.0.0.0",
        port=SERVER_PORT,
        reload=False,
        log_level="info"
    )