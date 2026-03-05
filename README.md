# 🎯 Number Guessing Telegram Bot

A feature-rich Telegram bot for group chats that hosts number guessing games with admin controls, leaderboards, and event management.

## ✨ Features

### 🎮 Game Features
- **Admin-controlled games**: Only admins can start/stop games
- **Custom event purposes**: Set event descriptions (e.g., "Giveaway: 1 Discord Nitro")
- **Multiple range options**: 1-1,000 to 1-50,000
- **@everyone notifications**: Announce new events to all members
- **Real-time feedback**: Instant "Too high/low" responses

### 🏆 Leaderboard & Statistics
- **Win streaks tracking**: Track consecutive wins
- **User statistics**: Personal win rates and game history
- **Global leaderboard**: Top players across all games
- **Game analytics**: Average guesses, completion rates

### 🛠️ Admin Commands
- `/start` - Start a new game with purpose and range selection
- `/stop` - Stop the current active game
- `/stats` - View game and personal statistics
- `/leaderboard` - Show top players
- `/history` - View recent guesses in current game
- `/help` - Get help information

### 🎯 Player Experience
- **Simple guessing**: Type `/number` to guess (e.g., `/42`)
- **Smart validation**: Ensures guesses are within range
- **Rich feedback**: Detailed responses with game context
- **Winner announcements**: Celebrate victories with @everyone tags

## 🚀 Quick Start

### 1. Get Your Bot Token
1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Use `/newbot` command
3. Follow instructions to get your bot token

### 2. Setup Environment
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your bot token
BOT_TOKEN=your_actual_bot_token_here
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Bot
```bash
python main.py
```

## 📦 Deployment to Render

### 1. Create GitHub Repository
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/number-guessing-bot.git
git push -u origin main
```

### 2. Deploy to Render
1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Set build command: `pip install -r requirements.txt`
5. Set start command: `python main.py`
6. Add environment variable: `BOT_TOKEN=your_bot_token`
7. Deploy!

### 3. Environment Variables on Render
- `BOT_TOKEN` - Your Telegram bot token (required)
- `PORT` - Port for webhooks (optional, default: 8000)
- `WEBHOOK_URL` - Webhook URL (optional, for production)

## 🎮 How to Use

### For Admins
1. **Start a game**: Use `/start` command
2. **Set purpose**: Describe what the event is for
3. **Choose range**: Select from available number ranges
4. **Monitor**: Use `/stats`, `/leaderboard`, `/history` to track progress

### For Players
1. **Guess numbers**: Type `/your_number` (e.g., `/42`)
2. **Get feedback**: Receive "Too high", "Too low", or "Correct!" responses
3. **Track progress**: Use `/stats` to see your personal statistics
4. **Compete**: Climb the leaderboard with consecutive wins

## 🏗️ Project Structure

```
├── main.py              # Main bot application
├── database.py          # Database management
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
└── README.md           # This file
```

## 🔧 Technical Details

### Database Schema
- **games**: Active and completed games with metadata
- **guesses**: Individual guess history with feedback
- **users**: Player statistics and streaks

### Bot Framework
- **python-telegram-bot**: Version 20.7
- **SQLite**: Local database storage
- **Async/await**: Non-blocking operations

### Security Features
- **Admin-only commands**: Only group admins can start/stop games
- **Input validation**: Range checking and format validation
- **Environment variables**: Secure token storage

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

If you encounter issues:
1. Check the bot has admin permissions in your group
2. Verify your bot token is correct
3. Ensure the bot can send messages and @everyone mentions
4. Check logs for error messages

## 🎉 Enjoy!

Start hosting exciting number guessing events in your Telegram groups today!