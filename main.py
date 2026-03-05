import os
import logging
import random
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    ConversationHandler
)
from database import DatabaseManager
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Conversation states
AWAITING_PURPOSE, AWAITING_RANGE = range(2)

# Range options
RANGE_OPTIONS = {
    '1000': (1, 1000),
    '5000': (1, 5000),
    '10000': (1, 10000),
    '20000': (1, 20000),
    '50000': (1, 50000)
}

class NumberGuessingBot:
    def __init__(self, token):
        self.token = token
        self.db = DatabaseManager()
        self.app = Application.builder().token(token).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Set up all command and message handlers"""
        
        # Start command handler
        self.app.add_handler(CommandHandler("start", self.start_game))
        
        # Admin commands
        admin_commands = [
            CommandHandler("stop", self.stop_game),
            CommandHandler("stats", self.show_stats),
            CommandHandler("leaderboard", self.show_leaderboard),
            CommandHandler("history", self.show_history),
            CommandHandler("help", self.show_help)
        ]
        
        for handler in admin_commands:
            self.app.add_handler(handler)
        
        # Message handler for guesses
        self.app.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            self.handle_guess
        ))
        
        # Callback query handler for range selection
        self.app.add_handler(CallbackQueryHandler(self.handle_range_selection))
    
    async def start_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start a new game - admin only"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        user_name = update.effective_user.full_name
        
        # Check if user is admin
        if not await self.is_admin(update, user_id):
            await update.message.reply_text("❌ Only admins can start games!")
            return
        
        # Check if there's already an active game
        active_game = self.db.get_active_game(str(chat_id))
        if active_game:
            await update.message.reply_text(
                f"❌ There's already an active game started by {active_game['admin_name']}!"
            )
            return
        
        await update.message.reply_text(
            "🎉 Starting a new game!\n\n"
            "📝 What is the purpose of this event? (e.g., 'Giveaway: 1 Discord Nitro')"
        )
        
        # Set conversation state
        context.user_data['awaiting_purpose'] = True
        context.user_data['admin_id'] = user_id
        context.user_data['admin_name'] = user_name
        context.user_data['chat_id'] = chat_id
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle messages during conversation"""
        if context.user_data.get('awaiting_purpose'):
            purpose = update.message.text.strip()
            if len(purpose) > 100:
                await update.message.reply_text("📝 Purpose too long! Please keep it under 100 characters.")
                return
            
            context.user_data['purpose'] = purpose
            context.user_data['awaiting_purpose'] = False
            
            # Show range selection buttons
            keyboard = [
                [InlineKeyboardButton("1-1,000", callback_data='1000'),
                 InlineKeyboardButton("1-5,000", callback_data='5000')],
                [InlineKeyboardButton("1-10,000", callback_data='10000'),
                 InlineKeyboardButton("1-20,000", callback_data='20000')],
                [InlineKeyboardButton("1-50,000", callback_data='50000')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"🎯 Purpose set: *{purpose}*\n\n"
                "🔢 Choose the number range:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def handle_range_selection(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle range selection via callback"""
        query = update.callback_query
        await query.answer()
        
        range_key = query.data
        if range_key not in RANGE_OPTIONS:
            await query.edit_message_text("❌ Invalid range selected!")
            return
        
        range_min, range_max = RANGE_OPTIONS[range_key]
        purpose = context.user_data.get('purpose', 'Unknown Event')
        chat_id = context.user_data['chat_id']
        admin_id = context.user_data['admin_id']
        admin_name = context.user_data['admin_name']
        
        # Generate random number
        target_number = random.randint(range_min, range_max)
        
        # Start the game in database
        success, result = self.db.start_game(
            str(chat_id), str(admin_id), admin_name, purpose, range_min, range_max, target_number
        )
        
        if not success:
            await query.edit_message_text(f"❌ Error starting game: {result}")
            return
        
        game_id = result
        
        # Create announcement message
        announcement = (
            f"🎉 *NEW EVENT STARTED!* 🎉\n\n"
            f"🏆 *{purpose}*\n"
            f"🎯 Range: {range_min:,} - {range_max:,}\n"
            f"👑 Started by: {admin_name}\n\n"
            f"💡 *How to play:*\n"
            f"Type `/your_number` to guess (e.g., `/42`)\n\n"
            f"Good luck! @everyone"
        )
        
        await query.edit_message_text(announcement, parse_mode='Markdown')
        
        # Clear conversation state
        context.user_data.clear()
        
        logger.info(f"Game started in chat {chat_id} by {admin_name} for '{purpose}' with range {range_min}-{range_max}")
    
    async def handle_guess(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle number guesses"""
        message = update.message.text.strip()
        
        # Check if it's a guess command (starts with /)
        if not message.startswith('/'):
            return
        
        try:
            guess_number = int(message[1:])  # Remove the / and convert to int
        except ValueError:
            return  # Not a valid number guess
        
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        user_name = update.effective_user.full_name
        
        # Get active game
        active_game = self.db.get_active_game(str(chat_id))
        if not active_game:
            return  # No active game
        
        target_number = active_game['target_number']
        range_min = active_game['range_min']
        range_max = active_game['range_max']
        
        # Validate guess range
        if guess_number < range_min or guess_number > range_max:
            await update.message.reply_text(
                f"❌ Number must be between {range_min:,} and {range_max:,}!"
            )
            return
        
        # Determine feedback
        if guess_number == target_number:
            feedback = "🎉 *CORRECT!* 🎉"
            is_winner = True
        elif guess_number < target_number:
            feedback = "📈 *Too low!* Try a higher number."
            is_winner = False
        else:
            feedback = "📉 *Too high!* Try a lower number."
            is_winner = False
        
        # Record the guess
        self.db.record_guess(active_game['id'], str(user_id), user_name, guess_number, feedback)
        
        # Send feedback
        await update.message.reply_text(
            f"{feedback}\n"
            f"Your guess: *{guess_number:,}*\n"
            f"Range: {range_min:,} - {range_max:,}",
            parse_mode='Markdown'
        )
        
        # Handle winner
        if is_winner:
            self.db.end_game(active_game['id'], str(user_id), user_name)
            
            # Get winner stats
            user_stats = self.db.get_user_stats(str(user_id))
            
            winner_message = (
                f"🎊 *CONGRATULATIONS!* 🎊\n\n"
                f"🏆 *{user_name}* won the game!\n"
                f"🎯 The number was: *{target_number:,}*\n"
                f"🎉 *{active_game['purpose']}*\n\n"
                f"📊 *Winner Stats:*\n"
                f"• Total Wins: {user_stats['total_wins']}\n"
                f"• Current Streak: {user_stats['current_streak']}\n"
                f"• Longest Streak: {user_stats['longest_streak']}\n\n"
                f"🎊 @everyone {user_name} is the winner! 🎊"
            )
            
            await update.message.reply_text(winner_message, parse_mode='Markdown')
            
            logger.info(f"User {user_name} won game {active_game['id']} with number {target_number}")
    
    async def stop_game(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Stop the current game - admin only"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        
        if not await self.is_admin(update, user_id):
            await update.message.reply_text("❌ Only admins can stop games!")
            return
        
        active_game = self.db.get_active_game(str(chat_id))
        if not active_game:
            await update.message.reply_text("❌ No active game to stop!")
            return
        
        # End the game
        self.db.end_game(active_game['id'], None, None)
        
        await update.message.reply_text(
            f"🛑 Game stopped by admin!\n"
            f"🎯 The number was: {active_game['target_number']:,}\n"
            f"🏆 Purpose: {active_game['purpose']}"
        )
    
    async def show_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show game statistics"""
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id
        user_name = update.effective_user.full_name
        
        # Get chat stats
        chat_stats = self.db.get_game_stats(str(chat_id))
        
        # Get user stats
        user_stats = self.db.get_user_stats(str(user_id))
        
        if user_stats:
            user_info = (
                f"👤 *Your Stats:*\n"
                f"• Total Wins: {user_stats['total_wins']}\n"
                f"• Current Streak: {user_stats['current_streak']}\n"
                f"• Longest Streak: {user_stats['longest_streak']}\n"
                f"• Total Games: {user_stats['total_games']}\n\n"
            )
        else:
            user_info = f"👤 *Your Stats:*\n• No games played yet!\n\n"
        
        stats_message = (
            f"📊 *Game Statistics*\n\n"
            f"{user_info}"
            f"📈 *Chat Stats:*\n"
            f"• Total Games: {chat_stats['total_games']}\n"
            f"• Completed Games: {chat_stats['completed_games']}\n"
            f"• Average Guesses per Game: {chat_stats['avg_guesses_per_game']}\n\n"
            f"💡 Use /leaderboard to see top players!"
        )
        
        await update.message.reply_text(stats_message, parse_mode='Markdown')
    
    async def show_leaderboard(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show the leaderboard"""
        leaderboard = self.db.get_leaderboard()
        
        if not leaderboard:
            await update.message.reply_text("📊 No games played yet! Start a game to see the leaderboard.")
            return
        
        message = "🏆 *LEADERBOARD* 🏆\n\n"
        for i, (name, wins, current_streak, longest_streak, total_games) in enumerate(leaderboard, 1):
            message += (
                f"{i}. *{name}*\n"
                f"   🏅 Wins: {wins} | 🔥 Streak: {current_streak} | 📈 Best: {longest_streak}\n\n"
            )
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def show_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show recent guess history"""
        chat_id = update.effective_chat.id
        active_game = self.db.get_active_game(str(chat_id))
        
        if not active_game:
            await update.message.reply_text("❌ No active game to show history for!")
            return
        
        history = self.db.get_guess_history(active_game['id'], 5)
        
        if not history:
            await update.message.reply_text("📝 No guesses recorded yet!")
            return
        
        message = "📜 *Recent Guesses* 📜\n\n"
        for name, guess, feedback, timestamp in history:
            message += f"• *{name}*: {guess:,} - {feedback}\n"
        
        await update.message.reply_text(message, parse_mode='Markdown')
    
    async def show_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show help information"""
        help_text = (
            "🆘 *Number Guessing Bot Help*\n\n"
            "🎮 *For Admins:*\n"
            "• /start - Start a new game (requires purpose and range)\n"
            "• /stop - Stop the current game\n"
            "• /stats - Show game statistics\n"
            "• /leaderboard - Show top players\n"
            "• /history - Show recent guesses\n"
            "• /help - Show this help\n\n"
            "🎯 *For Players:*\n"
            "• Type `/number` to guess (e.g., `/42`)\n"
            "• Get feedback: 'Too high', 'Too low', or 'Correct!'\n"
            "• Win streaks and leaderboard tracking\n\n"
            "💡 *Tips:*\n"
            "• Use binary search strategy for faster wins\n"
            "• Higher ranges = more challenging games\n"
            "• Track your progress on the leaderboard!"
        )
        
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    async def is_admin(self, update: Update, user_id: str) -> bool:
        """Check if user is admin"""
        try:
            chat_administrators = await update.effective_chat.get_administrators()
            admin_ids = [admin.user.id for admin in chat_administrators]
            return int(user_id) in admin_ids
        except:
            return False
    
    def run(self):
        """Start the bot"""
        logger.info("Starting Number Guessing Bot...")
        self.app.run_polling()

# Global bot instance for webhook access
bot = None

# Webhook setup for Render deployment
app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    """Webhook endpoint for Telegram"""
    try:
        json_data = await request.json()
        update = Update.de_json(json_data, bot.app.bot)
        await bot.app.process_update(update)
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "number-guessing-bot"}

# Initialize bot for webhook access (runs when module is imported)
def initialize_bot():
    global bot
    if bot is None:
        # Get bot token from environment variable
        bot_token = os.getenv('BOT_TOKEN')
        if not bot_token:
            logger.error("❌ Error: BOT_TOKEN environment variable not set!")
            return None
        
        # Initialize bot globally
        bot = NumberGuessingBot(bot_token)
        logger.info("Bot initialized for webhook access")
        return bot
    return bot

# Initialize bot when module is imported (for Render deployment)
initialize_bot()

if __name__ == '__main__':
    # Get bot token from environment variable
    bot_token = os.getenv('BOT_TOKEN')
    if not bot_token:
        print("❌ Error: BOT_TOKEN environment variable not set!")
        print("Please set your bot token as an environment variable.")
        exit(1)
    
    # Initialize bot globally
    bot = NumberGuessingBot(bot_token)
    
    # Check if running on Render (PORT environment variable)
    port = int(os.getenv('PORT', 8000))
    
    if os.getenv('RENDER'):
        # Running on Render - use webhook mode
        print("🚀 Starting bot in webhook mode for Render deployment...")
        uvicorn.run(app, host="0.0.0.0", port=port)
    else:
        # Local development - use polling mode
        print("🔧 Starting bot in polling mode for local development...")
        bot.run()
