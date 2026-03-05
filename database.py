import sqlite3
import logging
from datetime import datetime

class DatabaseManager:
    def __init__(self, db_path="bot_database.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize the database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Create games table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS games (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        chat_id TEXT NOT NULL,
                        admin_id TEXT NOT NULL,
                        admin_name TEXT,
                        purpose TEXT,
                        range_min INTEGER,
                        range_max INTEGER,
                        target_number INTEGER,
                        status TEXT DEFAULT 'active',
                        started_at TIMESTAMP,
                        ended_at TIMESTAMP,
                        winner_id TEXT,
                        winner_name TEXT
                    )
                ''')
                
                # Create guesses table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS guesses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        game_id INTEGER,
                        user_id TEXT NOT NULL,
                        user_name TEXT,
                        guess_number INTEGER,
                        feedback TEXT,
                        guessed_at TIMESTAMP,
                        FOREIGN KEY (game_id) REFERENCES games (id)
                    )
                ''')
                
                # Create users table for leaderboard
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS users (
                        user_id TEXT PRIMARY KEY,
                        user_name TEXT,
                        total_wins INTEGER DEFAULT 0,
                        total_games INTEGER DEFAULT 0,
                        current_streak INTEGER DEFAULT 0,
                        longest_streak INTEGER DEFAULT 0,
                        total_guesses INTEGER DEFAULT 0
                    )
                ''')
                
                conn.commit()
                logging.info("Database initialized successfully")
                
        except Exception as e:
            logging.error(f"Error initializing database: {e}")
            raise
    
    def start_game(self, chat_id, admin_id, admin_name, purpose, range_min, range_max, target_number):
        """Start a new game"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Check if there's already an active game in this chat
                cursor.execute('''
                    SELECT id FROM games 
                    WHERE chat_id = ? AND status = 'active'
                ''', (chat_id,))
                
                if cursor.fetchone():
                    return False, "There's already an active game in this chat"
                
                # Insert new game
                cursor.execute('''
                    INSERT INTO games 
                    (chat_id, admin_id, admin_name, purpose, range_min, range_max, target_number, started_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (chat_id, admin_id, admin_name, purpose, range_min, range_max, target_number, datetime.now()))
                
                game_id = cursor.lastrowid
                conn.commit()
                
                return True, game_id
                
        except Exception as e:
            logging.error(f"Error starting game: {e}")
            return False, str(e)
    
    def get_active_game(self, chat_id):
        """Get the currently active game in a chat"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT id, admin_id, admin_name, purpose, range_min, range_max, target_number, started_at
                    FROM games 
                    WHERE chat_id = ? AND status = 'active'
                ''', (chat_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'id': result[0],
                        'admin_id': result[1],
                        'admin_name': result[2],
                        'purpose': result[3],
                        'range_min': result[4],
                        'range_max': result[5],
                        'target_number': result[6],
                        'started_at': result[7]
                    }
                return None
                
        except Exception as e:
            logging.error(f"Error getting active game: {e}")
            return None
    
    def record_guess(self, game_id, user_id, user_name, guess_number, feedback):
        """Record a guess for a game"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO guesses 
                    (game_id, user_id, user_name, guess_number, feedback, guessed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (game_id, user_id, user_name, guess_number, feedback, datetime.now()))
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error recording guess: {e}")
            return False
    
    def end_game(self, game_id, winner_id, winner_name):
        """End a game and update user statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                # Update game status
                cursor.execute('''
                    UPDATE games 
                    SET status = 'ended', ended_at = ?, winner_id = ?, winner_name = ?
                    WHERE id = ?
                ''', (datetime.now(), winner_id, winner_name, game_id))
                
                # Update user statistics
                cursor.execute('''
                    INSERT OR IGNORE INTO users (user_id, user_name)
                    VALUES (?, ?)
                ''', (winner_id, winner_name))
                
                cursor.execute('''
                    UPDATE users 
                    SET total_wins = total_wins + 1,
                        current_streak = current_streak + 1,
                        longest_streak = MAX(longest_streak, current_streak + 1),
                        total_games = total_games + 1
                    WHERE user_id = ?
                ''', (winner_id,))
                
                # Reset streak for other players in this game
                cursor.execute('''
                    UPDATE users 
                    SET current_streak = 0
                    WHERE user_id IN (
                        SELECT DISTINCT user_id FROM guesses WHERE game_id = ? AND user_id != ?
                    )
                ''', (game_id, winner_id))
                
                conn.commit()
                return True
                
        except Exception as e:
            logging.error(f"Error ending game: {e}")
            return False
    
    def get_guess_history(self, game_id, limit=10):
        """Get recent guesses for a game"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT user_name, guess_number, feedback, guessed_at
                    FROM guesses 
                    WHERE game_id = ?
                    ORDER BY guessed_at DESC
                    LIMIT ?
                ''', (game_id, limit))
                
                return cursor.fetchall()
                
        except Exception as e:
            logging.error(f"Error getting guess history: {e}")
            return []
    
    def get_leaderboard(self, limit=10):
        """Get the top players by wins"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT user_name, total_wins, current_streak, longest_streak, total_games
                    FROM users 
                    ORDER BY total_wins DESC, longest_streak DESC
                    LIMIT ?
                ''', (limit,))
                
                return cursor.fetchall()
                
        except Exception as e:
            logging.error(f"Error getting leaderboard: {e}")
            return []
    
    def get_user_stats(self, user_id):
        """Get statistics for a specific user"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT user_name, total_wins, current_streak, longest_streak, total_games
                    FROM users 
                    WHERE user_id = ?
                ''', (user_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'user_name': result[0],
                        'total_wins': result[1],
                        'current_streak': result[2],
                        'longest_streak': result[3],
                        'total_games': result[4]
                    }
                return None
                
        except Exception as e:
            logging.error(f"Error getting user stats: {e}")
            return None
    
    def get_game_stats(self, chat_id):
        """Get game statistics for a chat"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                
                cursor.execute('''
                    SELECT COUNT(*) as total_games,
                           COUNT(CASE WHEN status = 'ended' THEN 1 END) as completed_games,
                           AVG(CASE WHEN status = 'ended' THEN 
                               (SELECT COUNT(*) FROM guesses g WHERE g.game_id = games.id) 
                           END) as avg_guesses_per_game
                    FROM games 
                    WHERE chat_id = ?
                ''', (chat_id,))
                
                result = cursor.fetchone()
                if result:
                    return {
                        'total_games': result[0] or 0,
                        'completed_games': result[1] or 0,
                        'avg_guesses_per_game': round(result[2] or 0, 2)
                    }
                return {'total_games': 0, 'completed_games': 0, 'avg_guesses_per_game': 0}
                
        except Exception as e:
            logging.error(f"Error getting game stats: {e}")
            return {'total_games': 0, 'completed_games': 0, 'avg_guesses_per_game': 0}