import os
import logging
import random
import json
from datetime import datetime, timedelta
import requests
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
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.conversations = {}  # Store conversation state
    
    def send_message(self, chat_id, text, reply_markup=None, parse_mode=None):
        """Send a message using Telegram Bot API"""
        url = f"{self.base_url}/sendMessage"
        data = {
            'chat_id': chat_id,
            'text': text
        }
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        if parse_mode:
            data['parse_mode'] = parse_mode
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return None
    
    def edit_message_text(self, chat_id, message_id, text, reply_markup=None, parse_mode=None):
        """Edit a message using Telegram Bot API"""
        url = f"{self.base_url}/editMessageText"
        data = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text
        }
        if reply_markup:
            data['reply_markup'] = json.dumps(reply_markup)
        if parse_mode:
            data['parse_mode'] = parse_mode
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            return None
    
    def answer_callback_query(self, callback_query_id, text=None):
        """Answer a callback query"""
        url = f"{self.base_url}/answerCallbackQuery"
        data = {
            'callback_query_id': callback_query_id
        }
        if text:
            data['text'] = text
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Error answering callback query: {e}")
            return None
    
    def get_chat_administrators(self, chat_id):
        """Get chat administrators"""
        url = f"{self.base_url}/getChatAdministrators"
        data = {'chat_id': chat_id}
        
        try:
            response = requests.post(url, data=data)
            response.raise_for_status()
            return response.json().get('result', [])
        except Exception as e:
            logger.error(f"Error getting chat administrators: {e}")
            return []
    
    async def start_game(self, update):
        """Start a new game - admin only"""
        chat_id = update['message']['chat']['id']
        user_id = update['message']['from']['id']
        user_name = update['message']['from']['first_name']
        
        # Check if user is admin
        if not await self.is_admin(chat_id, user_id):
            self.send_message(chat_id, "❌ Only admins can start games!")
            return
        
        # Check if there's already an active game
        active_game = self.db.get_active_game(str(chat_id))
        if active_game:
            self.send_message(chat_id, f"❌ There's already an active game started by {active_game['admin_name']}!")
            return
        
        self.send_message(
            chat_id,
            "🎉 Starting a new game!\n\n📝 What is the purpose of this event? (e.g., 'Giveaway: 1 Discord Nitro')"
        )
        
        # Set conversation state
        self.conversations[str(chat_id)] = {
            'state': AWAITING_PURPOSE,
            'admin_id': user_id,
            'admin_name': user_name,
            'chat_id': chat_id
        }
    
    async def handle_message(self, update):
        """Handle messages during conversation"""
        chat_id = str(update['message']['chat']['id'])
        
        if chat_id in self.conversations and self.conversations[chat_id].get('state') == AWAITING_PURPOSE:
            purpose = update['message']['text'].strip()
            if len(purpose) > 100:
                self.send_message(chat_id, "📝 Purpose too long! Please keep it under 100 characters.")
                return
            
            self.conversations[chat_id]['purpose'] = purpose
            self.conversations[chat_id]['state'] = AWAITING_RANGE
            
            # Show range selection buttons
            keyboard = [
                [{"text": "1-1,000", "callback_data": "1000"},
                 {"text": "1-5,000", "callback_data": "5000"}],
                [{"text": "1-10,000", "callback_data": "10000"},
                 {"text": "1-20,000", "callback_data": "20000"}],
                [{"text": "1-50,000", "callback_data": "50000"}]
            ]
            reply_markup = {"inline_keyboard": keyboard}
            
            self.send_message(
                chat_id,
                f"🎯 Purpose set: *{purpose}*\n\n🔢 Choose the number range:",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
    
    async def handle_range_selection(self, update):
        """Handle range selection via callback"""
        query = update['callback_query']
        callback_query_id = query['id']
        range_key = query['data']
        message = query['message']
        chat_id = str(message['chat']['id'])
        
        # Answer the callback query
        self.answer_callback_query(callback_query_id)
        
        if range_key not in RANGE_OPTIONS:
            self.edit_message_text(chat_id, message['message_id'], "❌ Invalid range selected!")
            return
        
        if chat_id not in self.conversations:
            self.edit_message_text(chat_id, message['message_id'], "❌ Conversation state lost. Please start again.")
            return
        
        range_min, range_max = RANGE_OPTIONS[range_key]
        purpose = self.conversations[chat_id].get('purpose', 'Unknown Event')
        admin_id = self.conversations[chat_id]['admin_id']
        admin_name = self.conversations[chat_id]['admin_name']
        
        # Generate random number
        target_number = random.randint(range_min, range_max)
        
        # Start the game in database
        success, result = self.db.start_game(
            chat_id, str(admin_id), admin_name, purpose, range_min, range_max, target_number
        )
        
        if not success:
            self.edit_message_text(chat_id, message['message_id'], f"❌ Error starting game: {result}")
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
        
        self.edit_message_text(chat_id, message['message_id'], announcement, parse_mode='Markdown')
        
        # Clear conversation state
        del self.conversations[chat_id]
        
        logger.info(f"Game started in chat {chat_id} by {admin_name} for '{purpose}' with range {range_min}-{range_max}")
    
    async def handle_guess(self, update):
        """Handle number guesses"""
        message = update['message']['text'].strip()
        chat_id = update['message']['chat']['id']
        user_id = update['message']['from']['id']
        user_name = update['message']['from']['first_name']
        
        # Check if it's a guess command (starts with /)
        if not message.startswith('/'):
            return
        
        try:
            guess_number = int(message[1:])  # Remove the / and convert to int
        except ValueError:
            return  # Not a valid number guess
        
        # Check anti-spam cooldown (2 seconds)
        can_guess, remaining_time = self.db.check_cooldown(str(user_id), str(chat_id), cooldown_seconds=2)
        if not can_guess:
            self.send_message(
                chat_id,
                f"⏳ *Cooldown Active!* Please wait {remaining_time} seconds before guessing again."
            )
            return
        
        # Get active game
        active_game = self.db.get_active_game(str(chat_id))
        if not active_game:
            return  # No active game
        
        target_number = active_game['target_number']
        range_min = active_game['range_min']
        range_max = active_game['range_max']
        
        # Validate guess range
        if guess_number < range_min or guess_number > range_max:
            self.send_message(
                chat_id,
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
        self.send_message(
            chat_id,
            f"{feedback}\nYour guess: *{guess_number:,}*\nRange: {range_min:,} - {range_max:,}",
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
            
            self.send_message(chat_id, winner_message, parse_mode='Markdown')
            
            logger.info(f"User {user_name} won game {active_game['id']} with number {target_number}")
    
    async def stop_game(self, update):
        """Stop the current game - admin only"""
        chat_id = update['message']['chat']['id']
        user_id = update['message']['from']['id']
        
        if not await self.is_admin(chat_id, user_id):
            self.send_message(chat_id, "❌ Only admins can stop games!")
            return
        
        active_game = self.db.get_active_game(str(chat_id))
        if not active_game:
            self.send_message(chat_id, "❌ No active game to stop!")
            return
        
        # End the game
        self.db.end_game(active_game['id'], None, None)
        
        self.send_message(
            chat_id,
            f"🛑 Game stopped by admin!\n🎯 The number was: {active_game['target_number']:,}\n🏆 Purpose: {active_game['purpose']}"
        )
    
    async def show_stats(self, update):
        """Show game statistics"""
        chat_id = update['message']['chat']['id']
        user_id = update['message']['from']['id']
        user_name = update['message']['from']['first_name']
        
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
        
        self.send_message(chat_id, stats_message, parse_mode='Markdown')
    
    async def show_leaderboard(self, update):
        """Show the leaderboard"""
        leaderboard = self.db.get_leaderboard()
        
        if not leaderboard:
            self.send_message(update['message']['chat']['id'], "📊 No games played yet! Start a game to see the leaderboard.")
            return
        
        message = "🏆 *LEADERBOARD* 🏆\n\n"
        for i, (name, wins, current_streak, longest_streak, total_games) in enumerate(leaderboard, 1):
            message += (
                f"{i}. *{name}*\n"
                f"   🏅 Wins: {wins} | 🔥 Streak: {current_streak} | 📈 Best: {longest_streak}\n\n"
            )
        
        self.send_message(update['message']['chat']['id'], message, parse_mode='Markdown')
    
    async def show_history(self, update):
        """Show recent guess history"""
        chat_id = update['message']['chat']['id']
        active_game = self.db.get_active_game(str(chat_id))
        
        if not active_game:
            self.send_message(chat_id, "❌ No active game to show history for!")
            return
        
        history = self.db.get_guess_history(active_game['id'], 5)
        
        if not history:
            self.send_message(chat_id, "📝 No guesses recorded yet!")
            return
        
        message = "📜 *Recent Guesses* 📜\n\n"
        for name, guess, feedback, timestamp in history:
            message += f"• *{name}*: {guess:,} - {feedback}\n"
        
        self.send_message(chat_id, message, parse_mode='Markdown')
    
    async def show_help(self, update):
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
        
        self.send_message(update['message']['chat']['id'], help_text, parse_mode='Markdown')
    
    async def is_admin(self, chat_id, user_id):
        """Check if user is admin"""
        try:
            admins = self.get_chat_administrators(chat_id)
            admin_ids = [admin['user']['id'] for admin in admins]
            return int(user_id) in admin_ids
        except:
            return False

# Global bot instance for webhook access
bot = None

# Webhook setup for Render deployment
app = FastAPI()

@app.post("/webhook")
async def webhook(request: Request):
    """Webhook endpoint for Telegram"""
    try:
        # Initialize bot if not already done
        if bot is None:
            initialize_bot()
        
        json_data = await request.json()
        
        # Handle different types of updates
        if 'message' in json_data:
            message = json_data['message']
            text = message.get('text', '')
            
            if text.startswith('/start'):
                await bot.start_game(json_data)
            elif text.startswith('/stop'):
                await bot.stop_game(json_data)
            elif text.startswith('/stats'):
                await bot.show_stats(json_data)
            elif text.startswith('/leaderboard'):
                await bot.show_leaderboard(json_data)
            elif text.startswith('/history'):
                await bot.show_history(json_data)
            elif text.startswith('/help'):
                await bot.show_help(json_data)
            elif text.startswith('/'):
                await bot.handle_guess(json_data)
            else:
                await bot.handle_message(json_data)
        
        elif 'callback_query' in json_data:
            await bot.handle_range_selection(json_data)
        
        return JSONResponse(content={"status": "ok"})
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "number-guessing-bot"}

# Initialize bot for webhook access
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
        # Local development - use polling mode (not implemented in this version)
        print("🔧 This version only supports webhook mode. Use Render deployment.")
        exit(1)