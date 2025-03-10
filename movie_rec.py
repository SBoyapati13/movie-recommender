"""
International Movie Recommender Application

This application provides personalized movie recommendations
using The Movie Database (TMDb) API, with support for
international movie selections and user preferences.

Key Features:
- Multi-language movie searching
- Personalized recommendations
- User rating system
- International movie database
"""

import tkinter as tk
from tkinter import ttk, messagebox
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from collections import defaultdict, deque
import heapq
from PIL import Image, ImageTk
import io
import sqlite3
import os
import numpy as np
from datetime import datetime
from dotenv import load_dotenv
from functools import lru_cache
from typing import Dict, List, Optional, Tuple
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

# Load environment variables from .env file
load_dotenv()

class MovieDatabaseManager:
    """Manages database operations with caching optimizations"""
    def __init__(self, db_path="movie_data.db"):
        self.db_path = db_path
        self.initialize_database()

    def initialize_database(self):
        """Create database tables with proper indexing"""
        conn = sqlite3.connect(self.db_path)

        try:
            cursor = conn.cursor()
            
            # User table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    password_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )''')

            # Movie table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS movies (
                    movie_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    original_title TEXT,
                    original_language TEXT,
                    release_year TEXT,
                    plot_summary TEXT,
                    poster_path TEXT,
                    popularity_score REAL,
                    average_vote REAL,
                    production_region TEXT,
                    genres TEXT
                )''')

            # User ratings with composite index
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_ratings (
                    user_id TEXT,
                    movie_id TEXT,
                    rating INTEGER CHECK (rating BETWEEN 1 AND 5),
                    timestamp TEXT,
                    PRIMARY KEY (user_id, movie_id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id),
                    FOREIGN KEY (movie_id) REFERENCES movies (movie_id)
                )''')
            
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_ratings
                ON user_ratings(user_id, movie_id)
            ''')
            
            # User preferences with cache-friendly structure
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    language TEXT DEFAULT 'en-US',
                    region TEXT DEFAULT 'US',
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )''')
            
            conn.commit()

        except sqlite3.Error as e:
            print(f"Database initialization failed: {e}")

        finally:
            conn.close()

    @lru_cache(maxsize=128)
    def get_user_preferences(self, user_id):
        """Get cached user preferences"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT language, region 
                FROM user_preferences 
                WHERE user_id = ?''', (user_id,))
            return cursor.fetchone() or ('en-US', 'US')

        except sqlite3.Error as e:
            print(f"Preferences query failed: {e}")
            return ('en-US', 'US')

        finally:
            conn.close()

    def set_user_preferences(self, user_id, language, region):
        """Update preferences with cache invalidation"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_preferences 
                VALUES (?, ?, ?)''', (user_id, language, region))
            conn.commit()
            self.get_user_preferences.cache_clear()

        except sqlite3.Error as e:
            print(f"Preferences update failed: {e}")

        finally:
            conn.close()

    def save_user_rating(self, user_id, movie_id, rating):
        """Save user rating with validation"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            cursor.execute('''
                INSERT OR REPLACE INTO user_ratings 
                VALUES (?, ?, ?, ?)''', 
                (user_id, movie_id, rating, timestamp))
            conn.commit()

        except sqlite3.Error as e:
            print(f"Rating save failed: {e}")

        finally:
            conn.close()

    def get_user_ratings(self, user_id):
        """Get ratings as {movie_id: rating}"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT movie_id, rating 
                FROM user_ratings 
                WHERE user_id = ?''', (user_id,))
            return {row[0]: row[1] for row in cursor.fetchall()}

        except sqlite3.Error as e:
            print(f"Ratings query failed: {e}")
            return {}

        finally:
            conn.close()

    def save_movie(self, movie_data):
        """Save movie data to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
            
        try:    
            movie_id = f"tmdb-{movie_data['id']}"
            title = movie_data.get('title', '')
            original_title = movie_data.get('original_title', '')
            original_language = movie_data.get('original_language', '')
            release_year = movie_data.get('release_date', '')[:4] if movie_data.get('release_date') else ''
            plot_summary = movie_data.get('overview', '')
            poster_path = movie_data.get('poster_path', '')
            popularity_score = movie_data.get('popularity', 0)
            average_vote = movie_data.get('vote_average', 0)
            production_region = movie_data.get('production_countries', [{}])[0].get('iso_3166_1', '') if 'production_countries' in movie_data else ''
            
            # Extract genres as IDs
            genres = ''
            if 'genres' in movie_data and movie_data['genres']:
                genres = ','.join([str(genre['id']) for genre in movie_data['genres']])
            elif 'genre_ids' in movie_data and movie_data['genre_ids']:
                genres = ','.join([str(genre_id) for genre_id in movie_data['genre_ids']])
            
            cursor.execute('''
                INSERT OR REPLACE INTO movies 
                (movie_id, title, original_title, original_language, release_year, 
                plot_summary, poster_path, popularity_score, average_vote, production_region, genres)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
                (movie_id, title, original_title, original_language, release_year, 
                plot_summary, poster_path, popularity_score, average_vote, production_region, genres))
            
            conn.commit()
            return movie_id
            
        except sqlite3.Error as e:
            print(f"Movie save failed: {e}")
            return None
            
        finally:
            conn.close()
    
    def get_movie_details(self, movie_id):
        """Get movie details from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM movies WHERE movie_id = ?''', (movie_id,))
            result = cursor.fetchone()
            
            if result:
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, result))
            return None
            
        except sqlite3.Error as e:
            print(f"Movie details query failed: {e}")
            return None
            
        finally:
            conn.close()
    
    def get_rated_movies_with_details(self, user_id):
        """Get all rated movies with details for user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.title, r.rating
                FROM user_ratings r
                JOIN movies m ON r.movie_id = m.movie_id
                WHERE r.user_id = ?
                ORDER BY r.timestamp DESC''', (str(user_id),))
            return cursor.fetchall()
            
        except sqlite3.Error as e:
            print(f"Rated movies query failed: {e}")
            return []
            
        finally:
            conn.close()
    
    def determine_user_favorite_genres(self, user_id):
        """Determine user's favorite genres based on ratings"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.genres, r.rating
                FROM user_ratings r
                JOIN movies m ON r.movie_id = m.movie_id
                WHERE r.user_id = ? AND r.rating >= 4''', (user_id,))
            
            results = cursor.fetchall()
            if not results:
                return []
                
            genre_scores = defaultdict(int)
            for genres_str, rating in results:
                if genres_str:
                    for genre in genres_str.split(','):
                        try:
                            genre_id = int(genre.strip())
                            genre_scores[genre_id] += rating
                        except ValueError:
                            # Skip invalid genre entries
                            pass
            
            # Return top 3 genres by score
            return [genre_id for genre_id, _ in sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)[:3]]
            
        except sqlite3.Error as e:
            print(f"Favorite genres query failed: {e}")
            return []
            
        finally:
            conn.close()
    
    def clean_unused_posters(self):
        """Keep only movie posters for rated movies"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Find all movies that have ratings
            cursor.execute('''
                SELECT DISTINCT movie_id FROM user_ratings
            ''')
            rated_movie_ids = {row[0] for row in cursor.fetchall()}

            # Set poster_path to NULL for unrated movies
            if rated_movie_ids:
                placeholders = ','.join(['?'] * len(rated_movie_ids))
                sql = f'''
                    UPDATE movies
                    SET poster_path = NULL
                    WHERE movie_id NOT IN ({placeholders})
                '''
                cursor.execute(sql, tuple(rated_movie_ids))
            else:
                cursor.execute('''UPDATE movies SET poster_path = NULL''')
            conn.commit()

        except sqlite3.Error as e:
            print(f"Clean unused posters failed: {e}")
            
        finally:
            conn.close()

    # [New User Authentication Methods]
    def create_user(self, username, password):
        """Create new user with type-safe inserts"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Generate type-safe values
            user_id = str(uuid.uuid4())
            hashed_pw = str(generate_password_hash(password))
            created_at = datetime.now().isoformat()
            username = str(username)

            # Explicit type casting
            cursor.execute('''
                INSERT INTO users 
                (user_id, username, password_hash, created_at)
                VALUES (?, ?, ?, ?)
            ''', (str(user_id), str(username), str(hashed_pw), str(created_at)))

            # Insert preferences with explicit user_id type
            cursor.execute('''
                INSERT INTO user_preferences (user_id)
                VALUES (?)
            ''', (str(user_id),))

            conn.commit()
            return user_id
            
        except sqlite3.Error as e:
            print(f"Database Error: {str(e)}")
            return "database_error"
            
        finally:
            conn.close()

    def authenticate_user(self, username, password):
        """Verify user credentials"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, password_hash 
                FROM users 
                WHERE username = ?
            ''', (username,))
            result = cursor.fetchone()
            
            if result and check_password_hash(result[1], password):
                return result[0]  # Return user_id
            return False

        except sqlite3.Error:
            return False

# [New Login Window Class]
class LoginWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Movie Recommender - Login")
        self.root.geometry("300x200")
        
        self.setup_ui()
        self.db = MovieDatabaseManager()
        self.logged_in_user = None
        
    def setup_ui(self):
        ttk.Label(self.root, text="Username:").pack(pady=5)
        self.username = ttk.Entry(self.root)
        self.username.pack(pady=5)
        
        ttk.Label(self.root, text="Password:").pack(pady=5)
        self.password = ttk.Entry(self.root, show="*")
        self.password.pack(pady=5)
        
        btn_frame = ttk.Frame(self.root)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Login", command=self.handle_login).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Sign Up", command=self.handle_signup).pack(side=tk.LEFT, padx=5)
        
    def handle_login(self):
        username = self.username.get()
        password = self.password.get()
        
        if not username or not password:
            messagebox.showerror("Error", "Please fill in all fields")
            return
            
        user_id = self.db.authenticate_user(username, password)
        if user_id:
            self.logged_in_user = user_id
            self.root.destroy()
        else:
            messagebox.showerror("Error", "Invalid credentials")

    def handle_signup(self):
        username = self.username.get().strip()
        password = self.password.get().strip()
        
        if not username or not password:
            messagebox.showerror("Error", "Please fill in all fields")
            return
            
        if len(password) < 8:
            messagebox.showerror("Error", "Password must be at least 8 characters")
            return
            
        result = self.db.create_user(username, password)
        
        if result == "username_exists":
            messagebox.showerror("Error", "Username already exists")

        elif result == "database_error":
            messagebox.showerror("Error", "Database error. Please try again.")

        elif result:
            messagebox.showinfo("Success", "Account created successfully!")
            self.logged_in_user = result
            self.root.destroy()

class MovieDataFetcher:
    """
    Handles movie data retrieval from The Movie Database (TMDb) API.
    """

    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p/"
    DEFAULT_TIMEOUT = 10
    MAX_RETRIES = 3

    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.getenv("TMDB_API_KEY")
        if not self.api_key or self.api_key == "YOUR_TMDB_API_KEY":
            raise ValueError("Valid TMDb API key required")

        # Configure session with retries
        self.session = requests.Session()
        retry = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=0.3,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('https://', adapter)

        # Initialize genre cache
        self.genres: Dict[int, str] = {}
        self.load_genres()

    def load_genres(self) -> None:
        """Load genre mappings from TMDb API"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}/genre/movie/list",
                params={'api_key': self.api_key},
                timeout=self.DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            self.genres = {g['id']: g['name'] for g in response.json()['genres']}

        except requests.exceptions.RequestException as e:
            print(f"Failed to load genres: {e}")
            # Fallback to basic genre list
            self.genres = {
                28: "Action", 12: "Adventure", 16: "Animation",
                35: "Comedy", 80: "Crime", 18: "Drama"
            }

    def _make_request(self, endpoint: str, params: dict) -> Optional[dict]:
        """Centralized request handling with retries"""
        try:
            response = self.session.get(
                f"{self.BASE_URL}{endpoint}",
                params={**params, 'api_key': self.api_key},
                timeout=self.DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return None

    def search_movies(self, query: str, language: str = 'en-US', region: str = 'US', page: int = 1) -> List[dict]:
        """Search movies with query validation"""
        if not query.strip():
            query = "a"  # Default empty search
            
        response = self._make_request(
            "/search/movie",
            {
                'query': query,
                'language': language,
                'region': region,
                'page': page,
                'include_adult': 'false'
            }
        )

        return response.get('results', []) if response else []

    def get_movie_details(self, movie_id: int, language: str = 'en-US') -> Optional[dict]:
        """Get detailed movie information"""
        return self._make_request(
            f"/movie/{movie_id}",
            {
                'language': language,
                'append_to_response': 'credits,similar,videos'
            }
        )

    def get_discover_movies(self, genre_ids: List[int], language: str = 'en-US', region: str = 'US', page: int = 1) -> List[dict]:
        """Discover movies by genre IDs"""
        valid_genres = [str(gid) for gid in genre_ids if gid in self.genres]

        if not valid_genres:
            return []

        response = self._make_request(
            "/discover/movie",
            {
                'with_genres': ",".join(valid_genres),
                'language': language,
                'region': region,
                'page': page,
                'sort_by': 'popularity.desc'
            }
        )

        return response.get('results', []) if response else []

    def fetch_image(self, poster_path: str, size: str = 'w500') -> Optional[Image.Image]:
        """Fetch and cache movie poster"""
        if not poster_path:
            return None

        try:
            response = self.session.get(
                f"{self.IMAGE_BASE_URL}{size}{poster_path}",
                timeout=self.DEFAULT_TIMEOUT
            )
            response.raise_for_status()
            return Image.open(io.BytesIO(response.content))
        except requests.exceptions.RequestException as e:
            print(f"Image download failed: {e}")
            return None

class RecommendationEngine:
    def __init__(self, movie_database, movie_fetcher):
        self.db = movie_database
        self.fetcher = movie_fetcher
        self.genre_weights = defaultdict(float)
        self.mood_genre_map = {
            'happy': ['Comedy', 'Animation', 'Family'],
            'sad': ['Drama', 'Romance'],
            'adventurous': ['Adventure', 'Action', 'Fantasy'],
            'thoughtful': ['Documentary', 'History', 'War'],
            'relaxed': ['Music', 'Romance', 'Mystery']
        }

    def _calculate_hybrid_score(self, movie, user_id):
        """Calculate hybrid score using collaborative + content-based filtering"""
        # Content-based features
        content_score = 0
        movie_genres = set(movie.get('genre_ids', []))
        
        # Collaborative features from user preferences
        user_fav_genres = self.db.determine_user_favorite_genres(user_id)
        genre_overlap = len(movie_genres & set(user_fav_genres))
        
        # Weighted components
        popularity = movie.get('popularity', 0) / 100  # Normalize
        rating = movie.get('vote_average', 0) / 2  # Scale 0-5
        content_score = 0.6 * genre_overlap + 0.4 * len(movie_genres)/5
        
        return 0.4 * popularity + 0.3 * rating + 0.3 * content_score

    def _get_mood_filters(self, mood):
        """Convert mood to genre filters"""
        genre_names = self.mood_genre_map.get(mood.lower(), [])
        return [k for k, v in self.fetcher.genres.items() if v in genre_names]

    def get_recommendations(self, user_id, mood=None, limit=10):
        """Generate hybrid recommendations with mood support"""
        language, region = self.db.get_user_preferences(user_id)
        rated_ids = self.db.get_user_ratings(user_id).keys()
        
        # Base query based on mood or favorites
        if mood:
            genre_ids = self._get_mood_filters(mood)
            results = self.fetcher.get_discover_movies(genre_ids, language, region)
        else:
            favorite_genres = self.db.determine_user_favorite_genres(user_id)
            results = self.fetcher.get_discover_movies(favorite_genres, language, region)
        
        # Fallback to popular movies if no results
        if not results:
            results = self.fetcher.search_movies("", language, region, page=1)

        # Score and rank movies
        scored = []
        for movie in results:
            movie_id = f"tmdb-{movie['id']}"
            if movie_id in rated_ids:
                continue
            
            score = self._calculate_hybrid_score(movie, user_id)
            scored.append((-score, movie))  # Negative for min-heap

        # Get top recommendations
        heapq.heapify(scored)
        recommendations = []
        while scored and len(recommendations) < limit:
            recommendations.append(heapq.heappop(scored)[1])
            
        return recommendations[:limit]

class MovieRecommenderGUI:
    """
    Main GUI for the Movie Recommender application
    """
    def __init__(self, master, user_id):
        self.master = master
        self.current_user_id = user_id
        self.master.title("International Movie Recommender")
        self.master.geometry("1000x700")
        self.master.minsize(800, 600)

        # Load API key from environment or .env file
        self.api_key = os.getenv("TMDB_API_KEY")
        if not self.api_key:
            messagebox.showerror("API Key Missing", "Please set the TMDB_API_KEY environment variable.")
            self.master.destroy()  # Close the application
            return

        self.db = MovieDatabaseManager()
        self.movie_api = MovieDataFetcher(self.api_key)
        self.recommendation_engine = RecommendationEngine(self.db, self.movie_api)
        self.current_search_results = []
        self.current_recommendations = []
        self.poster_cache = {}

        # GUI setup
        self.setup_gui()
        # Load user preferences
        language, region = self.db.get_user_preferences(self.current_user_id)
        self.language_var = tk.StringVar(value=language)
        self.region_var = tk.StringVar(value=region)

        # Show initial recommendations
        self.update_recommendations()

        self.db.clean_unused_posters()

    def setup_gui(self):
        """Set up the main GUI components"""
        # Main frame
        self.main_frame = ttk.Frame(self.master, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.search_tab = ttk.Frame(self.notebook)
        self.recommendations_tab = ttk.Frame(self.notebook)
        self.ratings_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.search_tab, text="Search Movies")
        self.notebook.add(self.recommendations_tab, text="Recommendations")
        self.notebook.add(self.ratings_tab, text="My Ratings")
        self.notebook.add(self.settings_tab, text="Settings")

        # Set up each tab
        self.setup_search_tab()
        self.setup_recommendations_tab()
        self.setup_ratings_tab()
        self.setup_settings_tab()

        # Status bar
        self.status_bar = ttk.Label(self.main_frame, text=AttributionManager.get_attribution_text(),
                                  anchor=tk.W, padding=(0, 5))
        self.status_bar.pack(fill=tk.X, side=tk.BOTTOM)

        self.mood_var = tk.StringVar()
        self._add_mood_selector()

    def _add_mood_selector(self):
        """Add mood selection to recommendations tab"""
        mood_frame = ttk.Frame(self.recommendations_tab)
        mood_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(mood_frame, text="Current Mood:").pack(side=tk.LEFT)
        self.mood_combo = ttk.Combobox(mood_frame, 
                                      textvariable=self.mood_var,
                                      values=['Any'] + list(self.recommendation_engine.mood_genre_map.keys()))
        self.mood_combo.pack(side=tk.LEFT, padx=5)
        self.mood_combo.set('Any')
        
        ttk.Button(mood_frame, text="Apply Mood", 
                  command=self.update_recommendations).pack(side=tk.LEFT)

    def setup_search_tab(self):
        """Set up the Search tab"""
        # Top frame for search controls
        top_frame = ttk.Frame(self.search_tab, padding=10)
        top_frame.pack(fill=tk.X)

        # Search entry and button
        ttk.Label(top_frame, text="Search Movies:").pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind("<Return>", lambda e: self.search_movies())
        ttk.Button(top_frame, text="Search", command=self.search_movies).pack(side=tk.LEFT, padx=5)

        # Language and region filters
        ttk.Label(top_frame, text="Language:").pack(side=tk.LEFT, padx=(20, 5))
        self.language_var = tk.StringVar(value="en-US")
        language_options = list(LanguageManager.get_language_options().keys())
        language_dropdown = ttk.Combobox(top_frame, textvariable=self.language_var, values=language_options, width=10)
        language_dropdown.pack(side=tk.LEFT)

        ttk.Label(top_frame, text="Region:").pack(side=tk.LEFT, padx=(20, 5))
        self.region_var = tk.StringVar(value="US")
        region_options = list(LanguageManager.get_region_options().keys())
        region_dropdown = ttk.Combobox(top_frame, textvariable=self.region_var, values=region_options, width=10)
        region_dropdown.pack(side=tk.LEFT)

        # Search results container with scrollbar
        results_container = ttk.Frame(self.search_tab)
        results_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create canvas with scrollbar for results
        self.search_canvas = tk.Canvas(results_container)
        search_scrollbar = ttk.Scrollbar(results_container, orient="vertical", command=self.search_canvas.yview)
        
        self.search_results_frame = ttk.Frame(self.search_canvas)
        self.search_results_frame.bind("<Configure>", 
                                     lambda e: self.search_canvas.configure(scrollregion=self.search_canvas.bbox("all")))
        
        self.search_canvas.create_window((0, 0), window=self.search_results_frame, anchor="nw")
        self.search_canvas.configure(yscrollcommand=search_scrollbar.set)
        
        self.search_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        search_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def setup_recommendations_tab(self):
        """Set up the Recommendations tab"""
        rec_frame = ttk.Frame(self.recommendations_tab)
        rec_frame.pack(fill=tk.BOTH, expand=True)
        
        self.rec_canvas = tk.Canvas(rec_frame)
        rec_scrollbar = ttk.Scrollbar(rec_frame, orient=tk.VERTICAL, command=self.rec_canvas.yview)
        
        self.rec_results_frame = ttk.Frame(self.rec_canvas)
        self.rec_results_frame.bind("<Configure>", 
                                  lambda e: self.rec_canvas.configure(scrollregion=self.rec_canvas.bbox("all")))
        
        self.rec_canvas.create_window((0, 0), window=self.rec_results_frame, anchor=tk.NW)
        self.rec_canvas.configure(yscrollcommand=rec_scrollbar.set)
        
        self.rec_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        rec_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Refresh button for recommendations
        ttk.Button(self.recommendations_tab, text="Refresh Recommendations", 
                 command=self.update_recommendations).pack(side=tk.BOTTOM, pady=10)

    def setup_ratings_tab(self):
        """Set up the My Ratings tab"""
        ratings_frame = ttk.Frame(self.ratings_tab)
        ratings_frame.pack(fill=tk.BOTH, expand=True)
    
        # Add treeview for ratings
        self.ratings_tree = ttk.Treeview(ratings_frame, columns=('Movie', 'Rating'), show='headings')
        self.ratings_tree.heading('Movie', text='Movie Title')
        self.ratings_tree.heading('Rating', text='Your Rating')
        self.ratings_tree.column('Movie', width=400)
        self.ratings_tree.column('Rating', width=100, anchor=tk.CENTER)
        self.ratings_tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add a scrollbar
        ratings_scrollbar = ttk.Scrollbar(ratings_frame, orient=tk.VERTICAL, command=self.ratings_tree.yview)
        self.ratings_tree.configure(yscrollcommand=ratings_scrollbar.set)
        ratings_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Refresh button
        ttk.Button(self.ratings_tab, text="Refresh Ratings", 
                 command=self.populate_rated_movies).pack(side=tk.BOTTOM, pady=10)
        
        # Initial population of ratings
        self.populate_rated_movies()

    def setup_settings_tab(self):
        """Set up the Settings tab"""
        settings_frame = ttk.LabelFrame(self.settings_tab, text="User Preferences", padding=20)
        settings_frame.pack(padx=20, pady=20, fill=tk.X)
    
        ttk.Label(settings_frame, text="Preferred Language:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.lang_combo = ttk.Combobox(settings_frame, 
                                     textvariable=self.language_var,
                                     values=list(LanguageManager.get_language_options().keys()))
        self.lang_combo.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)
    
        ttk.Label(settings_frame, text="Region:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.region_combo = ttk.Combobox(settings_frame, 
                                       textvariable=self.region_var,
                                       values=list(LanguageManager.get_region_options().keys()))
        self.region_combo.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
    
        ttk.Button(settings_frame, text="Save Preferences", 
                 command=self.save_preferences).grid(row=2, columnspan=2, pady=20)
        
        # Database maintenance section
        maintenance_frame = ttk.LabelFrame(self.settings_tab, text="Database Maintenance", padding=20)
        maintenance_frame.pack(padx=20, pady=20, fill=tk.X)
        
        ttk.Button(maintenance_frame, text="Clean Unused Poster Images", 
                 command=self.clean_posters).pack(pady=10)

    def clean_posters(self):
        """Clean unused posters from database"""
        self.db.clean_unused_posters()
        messagebox.showinfo("Maintenance", "Unused poster images have been cleaned from the database.")

    def populate_rated_movies(self):
        """Populate ratings for CURRENT user"""
        for item in self.ratings_tree.get_children():
            self.ratings_tree.delete(item)

        rated_movies = self.db.get_rated_movies_with_details(self.current_user_id)
        for movie in rated_movies:
            self.ratings_tree.insert('', 'end', values=movie)

    def search_movies(self):
        """Handle movie search functionality"""
        try:
            query = self.search_var.get()
            lang = self.language_var.get()
            region = self.region_var.get()
            
            if not query:
                messagebox.showwarning("Empty Query", "Please enter a search term")
                return
                
            results = self.movie_api.search_movies(query, lang, region)
            self.current_search_results = results
            self.display_results(results)
            
            if not results:
                self.status_bar.config(text="No movies found for your search query.")
            else:
                self.status_bar.config(text=f"Found {len(results)} movies matching your search.")
        
        except Exception as e:
            messagebox.showerror("Search Error", f"Failed to search movies: {str(e)}")
            self.status_bar.config(text=f"Error: {str(e)}")

    def display_results(self, results):
        """Display search results in the search tab"""
        self.clear_results()
    
        for idx, movie in enumerate(results):
            frame = ttk.Frame(self.search_results_frame)
            frame.grid(row=idx, column=0, sticky=tk.W, pady=5, padx=5)
        
            # Poster image
            poster_img = self.load_poster_image(movie.get('poster_path'))
            if poster_img:
                label = ttk.Label(frame, image=poster_img)
                label.image = poster_img  # Keep reference
                label.grid(row=0, column=0, rowspan=3, padx=5)
            
            # Movie info
            ttk.Label(frame, text=movie['title'], font=('Arial', 12, 'bold')).grid(row=0, column=1, sticky=tk.W)
            ttk.Label(frame, text=f"TMDB Rating: {movie.get('vote_average', 'N/A')}").grid(row=1, column=1, sticky=tk.W)
            
            # Rating combobox (1-5 scale)
            rating_var = tk.StringVar()
            rating_combo = ttk.Combobox(frame, textvariable=rating_var, 
                                        values=[str(i) for i in range(1, 6)], width=3)
            rating_combo.grid(row=2, column=1, sticky=tk.W)
            
            # Save rating button
            ttk.Button(frame, text="Save Rating", 
                     command=lambda m=movie, r=rating_var: self.save_rating(m['id'], r.get())).grid(row=2, column=2, padx=5)

    def load_poster_image(self, poster_path):
        """Load and cache poster image"""
        if not poster_path:
            return None
        if poster_path in self.poster_cache:
            return self.poster_cache[poster_path]
        
        image = self.movie_api.fetch_image(poster_path)
        if image:
            image = image.resize((100, 150), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self.poster_cache[poster_path] = photo
            return photo
        return None

    def save_rating(self, tmdb_id, rating):
        """Save movie rating to database"""
        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                messagebox.showerror("Invalid Rating", "Please select a rating between 1 and 5.")
                return

            # Fetch movie details from API
            movie_data = self.movie_api.get_movie_details(tmdb_id)
            if not movie_data:
                messagebox.showerror("Error", "Failed to fetch movie details.")
                return

            # Save movie to database
            movie_id = self.db.save_movie(movie_data)
            if not movie_id:
                messagebox.showerror("Error", "Failed to save movie details.")
                return

            # Save user rating
            self.db.save_user_rating(self.current_user_id, movie_id, rating)
            self.populate_rated_movies()
            messagebox.showinfo("Success", "Rating saved successfully!")
            self.db.clean_unused_posters()  # Ensure only rated movies keep posters

        except ValueError:
            messagebox.showerror("Invalid Rating", "Please select a valid number between 1 and 5.")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save rating: {str(e)}")

    def update_recommendations(self):
        """Update with mood filter"""
        mood = self.mood_var.get() if self.mood_var.get() != 'Any' else None
        self.current_recommendations = self.recommendation_engine.get_recommendations(self.current_user_id, mood=mood)
        self.display_recommendations()

    def display_recommendations(self):
        """Display recommendations in the recommendations tab"""
        # Clear previous recommendations
        for widget in self.rec_results_frame.winfo_children():
            widget.destroy()
        
        for idx, movie in enumerate(self.current_recommendations):
            frame = ttk.Frame(self.rec_results_frame)
            frame.grid(row=idx, column=0, sticky=tk.W, pady=5, padx=5)
        
            # Poster image
            poster_img = self.load_poster_image(movie.get('poster_path'))
            if poster_img:
                label = ttk.Label(frame, image=poster_img)
                label.image = poster_img
                label.grid(row=0, column=0, rowspan=3, padx=5)
            
            # Movie info
            ttk.Label(frame, text=movie['title'], font=('Arial', 12, 'bold')).grid(row=0, column=1, sticky=tk.W)
            ttk.Label(frame, text=f"TMDB Rating: {movie.get('vote_average', 'N/A')}").grid(row=1, column=1, sticky=tk.W)
            
            # Rating combobox (1-5 scale)
            rating_var = tk.StringVar()
            rating_combo = ttk.Combobox(frame, textvariable=rating_var, 
                                        values=[str(i) for i in range(1, 6)], width=3)
            rating_combo.grid(row=2, column=1, sticky=tk.W)
            
            # Save rating button
            ttk.Button(frame, text="Save Rating", 
                     command=lambda m=movie, r=rating_var: self.save_rating(m['id'], r.get())).grid(row=2, column=2, padx=5)

    def clear_results(self):
        """Clear search results"""
        for widget in self.search_results_frame.winfo_children():
            widget.destroy()

    def save_preferences(self):
        """Save user preferences"""
        language = self.language_var.get()
        region = self.region_var.get()
        self.db.set_user_preferences(self.current_user_id, language, region)
        messagebox.showinfo("Preferences Saved", "Your preferences have been updated!")
        self.update_recommendations()

class AttributionManager:
    """
    Manages TMDb API attribution requirements.
    """
    @staticmethod
    def get_attribution_text():
        """Returns required attribution text"""
        return "This product uses the TMDb API but is not endorsed, certified, or otherwise approved by TMDb."

class LanguageManager:
    """
    Manages language and region options
    """
    @staticmethod
    def get_language_options():
        """Returns dictionary of language codes and names"""
        return {
            'en-US': 'English (US)',
            'es-ES': 'Español (Spain)',
            'fr-FR': 'Français (France)',
            'de-DE': 'Deutsch (Germany)',
            'it-IT': 'Italiano (Italy)',
            'ja-JP': '日本語 (Japan)',
            'ko-KR': '한국어 (Korea)',
            'pt-BR': 'Português (Brazil)',
            'ru-RU': 'Русский (Russia)',
            'zh-CN': '中文 (China)'
        }

    @staticmethod
    def get_region_options():
        """Returns dictionary of region codes and names"""
        return {
            'US': 'United States',
            'GB': 'United Kingdom',
            'CA': 'Canada',
            'FR': 'France',
            'DE': 'Germany',
            'ES': 'Spain',
            'IT': 'Italy',
            'JP': 'Japan',
            'KR': 'South Korea',
            'BR': 'Brazil',
            'RU': 'Russia',
            'CN': 'China',
            'IN': 'India',
            'AU': 'Australia',
            'MX': 'Mexico'
        }

if __name__ == "__main__":
    login_window = LoginWindow()
    login_window.root.mainloop()

    if login_window.logged_in_user:
        root = tk.Tk()
        app = MovieRecommenderGUI(root, login_window.logged_in_user)
        root.mainloop()