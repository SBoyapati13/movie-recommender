"""
International Movie Recommender (TMDb Compliant Version)

This application strictly follows TMDb API guidelines and requirements:
- Proper error handling and rate limiting
- Correct API parameter usage
- Required attribution display
- Efficient caching strategies
- Compliance with TMDb terms of service
"""

import tkinter as tk
from tkinter import ttk, messagebox, Frame
import json
import requests
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from PIL import Image, ImageTk
import io
import os
import time
import threading
from functools import lru_cache
import urllib.request

# TMDb API Configuration
TMDB_API_VERSION = "3"
TMDB_BASE_URL = f"https://api.themoviedb.org/{TMDB_API_VERSION}"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/"

class TMDbClient:
    """Official TMDb API client following documentation guidelines"""
    
    def __init__(self, api_key):
        if not api_key:
            raise ValueError("Valid TMDb API key required")
        self.api_key = api_key
        self.session = requests.Session()
        self.rate_limit_reset = 0
        self.genre_cache = {}
        self._initialize_genres()
        
    def _initialize_genres(self):
        """Cache genre list as recommended by TMDb documentation"""
        endpoint = "/genre/movie/list"
        response = self._api_request(endpoint)
        self.genre_cache = {g['id']: g['name'] for g in response.get('genres', [])}
    
    def _api_request(self, endpoint, params=None, retries=3):
        """Handle API requests with proper error handling and rate limiting"""
        if time.time() < self.rate_limit_reset:
            time.sleep(1)
            
        url = f"{TMDB_BASE_URL}{endpoint}"
        params = params or {}
        params['api_key'] = self.api_key
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            
            # Handle rate limits
            if response.status_code == 429:
                self.rate_limit_reset = time.time() + int(response.headers.get('Retry-After', 10))
                if retries > 0:
                    time.sleep(1)
                    return self._api_request(endpoint, params, retries-1)
                raise Exception("Rate limit exceeded")
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"API Error: {str(e)}")
            return {}

    def search_movies(self, query, language='en-US', region='US', page=1):
        """TMDb-compliant movie search"""
        params = {
            'query': query,
            'language': language,
            'region': region,
            'page': page,
            'include_adult': 'false'
        }
        return self._api_request("/search/movie", params)

    def get_movie_details(self, movie_id, language='en-US'):
        """Get movie details with proper append_to_response"""
        return self._api_request(f"/movie/{movie_id}", {
            'language': language,
            'append_to_response': 'credits,similar'
        })

    def get_recommendations(self, movie_id, language='en-US'):
        """Get TMDb official recommendations"""
        return self._api_request(f"/movie/{movie_id}/recommendations", {
            'language': language
        })

    def discover_movies(self, genres=None, language='en-US', region='US'):
        """Proper discover implementation with genre handling"""
        params = {
            'language': language,
            'region': region,
            'sort_by': 'popularity.desc',
            'with_genres': ','.join(map(str, genres)) if genres else ''
        }
        return self._api_request("/discover/movie", params)
        
    def get_trending_movies(self, time_window='week'):
        """Get trending movies for the specified time window (day or week)"""
        return self._api_request(f"/trending/movie/{time_window}")

class MovieDatabase:
    """TMDb-compliant data storage following API guidelines"""
    
    def __init__(self, db_path='tmdb_cache.db'):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    tmdb_id INTEGER PRIMARY KEY,
                    data TEXT,
                    last_updated TIMESTAMP
                )""")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_data (
                    user_id INTEGER,
                    tmdb_id INTEGER,
                    rating REAL,
                    timestamp TIMESTAMP,
                    PRIMARY KEY(user_id, tmdb_id)
                )""")

    def cache_movie(self, tmdb_id, data):
        """Temporary cache following TMDb storage guidelines"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO movies 
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (tmdb_id, json.dumps(data)))

    def get_cached_movie(self, tmdb_id):
        """Retrieve cached movie data if not expired (24 hours)"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute("""
                SELECT data, last_updated FROM movies WHERE tmdb_id=?
            """, (tmdb_id,)).fetchone()
            
            if not result:
                return None
                
            data, timestamp = result
            cache_time = datetime.fromisoformat(timestamp)
            
            # Check if cache is valid (less than 24 hours old)
            if datetime.now() - cache_time < timedelta(hours=24):
                return json.loads(data)
            return None
            
    def save_user_rating(self, user_id, tmdb_id, rating):
        """Save user rating for a movie"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_data
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (user_id, tmdb_id, rating))
            
    def get_user_ratings(self, user_id):
        """Get all ratings for a specific user"""
        with sqlite3.connect(self.db_path) as conn:
            results = conn.execute("""
                SELECT tmdb_id, rating FROM user_data
                WHERE user_id = ?
            """, (user_id,)).fetchall()
            return {tmdb_id: rating for tmdb_id, rating in results}

class ImageCache:
    """Caches poster images to avoid repeated downloads"""
    
    def __init__(self, cache_dir='image_cache'):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
    
    def get_poster(self, poster_path, size='w185'):
        """Get movie poster from cache or download if not available"""
        if not poster_path:
            return None
            
        cache_path = os.path.join(self.cache_dir, f"{size}_{poster_path.lstrip('/')}")
        
        # Return cached image if exists
        if os.path.exists(cache_path):
            try:
                return ImageTk.PhotoImage(Image.open(cache_path))
            except Exception:
                # If the image is corrupted, remove it and continue to download
                os.remove(cache_path)
        
        # Download and cache image
        try:
            image_url = f"{TMDB_IMAGE_BASE}{size}{poster_path}"
            response = urllib.request.urlopen(image_url)
            image_data = response.read()
            
            # Save to cache
            with open(cache_path, 'wb') as f:
                f.write(image_data)
                
            # Create PhotoImage
            return ImageTk.PhotoImage(Image.open(io.BytesIO(image_data)))
        except Exception as e:
            print(f"Error loading image: {str(e)}")
            return None

class ScrollableFrame(ttk.Frame):
    """A scrollable frame for displaying multiple movie cards"""
    
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        
        # Create a canvas and scrollbar
        self.canvas = tk.Canvas(self)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Configure canvas
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Mouse wheel scrolling
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
        
        # Canvas should expand to fill available space
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        
        # Pack elements
        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
    def _on_canvas_configure(self, event):
        # Update the width of the canvas frame
        self.canvas.itemconfig(self.canvas_frame, width=event.width)
    
    def _bind_mousewheel(self, event):
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
    def _unbind_mousewheel(self, event):
        self.canvas.unbind_all("<MouseWheel>")
        
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

class RecommendationEngine:
    """TMDb-based recommendation system with proper attribution"""
    
    def __init__(self, tmdb_client, db):
        self.tmdb = tmdb_client
        self.db = db
        
    def generate_recommendations(self, user_id=1, limit=10):
        """Generate personalized recommendations based on user ratings"""
        # Get user's rated movies
        user_ratings = self.db.get_user_ratings(user_id)
        
        if not user_ratings:
            # If no ratings, return trending movies
            return self.tmdb.get_trending_movies().get('results', [])[:limit]
        
        # Get recommendations based on highest-rated movies
        recommended_movies = []
        
        # Sort by rating (highest first)
        sorted_ratings = sorted(user_ratings.items(), key=lambda x: x[1], reverse=True)
        
        # Get recommendations for top 3 movies
        for movie_id, _ in sorted_ratings[:3]:
            recs = self.tmdb.get_recommendations(movie_id).get('results', [])
            recommended_movies.extend(recs)
            
        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        
        for movie in recommended_movies:
            if movie['id'] not in seen and movie['id'] not in user_ratings:
                seen.add(movie['id'])
                unique_recommendations.append(movie)
                
                if len(unique_recommendations) >= limit:
                    break
                    
        return unique_recommendations

class MovieRecommenderApp(tk.Tk):
    """GUI following TMDb brand guidelines"""
    
    def __init__(self, api_key):
        super().__init__()
        self.title("Movie Recommender (Powered by TMDb)")
        self.geometry("1000x700")
        self.minsize(800, 600)
        
        # Initialize components
        self.tmdb = TMDbClient(api_key)
        self.db = MovieDatabase()
        self.image_cache = ImageCache()
        self.engine = RecommendationEngine(self.tmdb, self.db)
        self.current_user_id = 1  # Default user
        
        # Default placeholder image
        self.placeholder_image = None
        self._create_placeholder_image()
        
        # Set up styles
        self._setup_styles()
        
        # Setup UI
        self._create_widgets()
        self._show_attribution()
        
        # Load initial recommendations
        self.load_recommendations()
        
    def _create_placeholder_image(self):
        """Create a placeholder image for movies without posters"""
        img = Image.new('RGB', (185, 278), color=(200, 200, 200))
        self.placeholder_image = ImageTk.PhotoImage(img)
        
    def _setup_styles(self):
        """Set up ttk styles for the application"""
        style = ttk.Style()
        style.configure("Card.TFrame", background="#f0f0f0", relief="raised", borderwidth=1)
        style.configure("Title.TLabel", font=("Helvetica", 12, "bold"))
        style.configure("Year.TLabel", font=("Helvetica", 10), foreground="#555555")
        style.configure("Rating.TLabel", font=("Helvetica", 10, "bold"), foreground="#01b4e4")
        
    def _create_widgets(self):
        # Main notebook interface
        self.notebook = ttk.Notebook(self)
        
        # Search tab
        self.search_frame = ttk.Frame(self.notebook)
        self._build_search_interface()
        
        # Recommendations tab
        self.rec_frame = ttk.Frame(self.notebook)
        self._build_recommendation_interface()
        
        self.notebook.add(self.search_frame, text="Search Movies")
        self.notebook.add(self.rec_frame, text="Recommendations")
        self.notebook.pack(expand=True, fill=tk.BOTH, padx=10, pady=10)
        
    def _build_search_interface(self):
        # Search controls
        search_panel = ttk.Frame(self.search_frame)
        ttk.Label(search_panel, text="Search for movies:").pack(side=tk.LEFT, padx=(0, 10))
        self.search_entry = ttk.Entry(search_panel, width=40)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<Return>", lambda e: self._perform_search())
        
        search_button = ttk.Button(search_panel, text="Search", command=self._perform_search)
        search_button.pack(side=tk.LEFT, padx=5)
        
        search_panel.pack(fill=tk.X, pady=10)
        
        # Results display
        self.results_frame = ScrollableFrame(self.search_frame)
        self.results_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
    def _build_recommendation_interface(self):
        # Title and refresh button
        header_frame = ttk.Frame(self.rec_frame)
        ttk.Label(header_frame, text="Recommended Movies", font=("Helvetica", 14, "bold")).pack(side=tk.LEFT)
        ttk.Button(header_frame, text="Refresh", command=self.load_recommendations).pack(side=tk.RIGHT)
        header_frame.pack(fill=tk.X, pady=10)
        
        # Recommendation display grid
        self.rec_container = ScrollableFrame(self.rec_frame)
        self.rec_container.pack(fill=tk.BOTH, expand=True)
        
    def _show_attribution(self):
        # Proper TMDb attribution
        attr_frame = ttk.Frame(self)
        # Add TMDb logo here in a production app
        attr_label = ttk.Label(attr_frame, 
            text="This product uses the TMDb API but is not endorsed or certified by TMDb",
            foreground="#01b4e4"
        )
        attr_label.pack(pady=10)
        attr_frame.pack(side=tk.BOTTOM, fill=tk.X)
        
    def _perform_search(self):
        # Implement proper search with error handling
        query = self.search_entry.get().strip()
        if not query:
            messagebox.showinfo("Search", "Please enter a movie title to search")
            return
        
        # Clear previous results
        for widget in self.results_frame.scrollable_frame.winfo_children():
            widget.destroy()
            
        # Show loading indicator
        loading_label = ttk.Label(self.results_frame.scrollable_frame, text="Searching...")
        loading_label.pack(pady=20)
        self.update()
        
        try:
            results = self.tmdb.search_movies(query)
            loading_label.destroy()
            self._display_search_results(results.get('results', []))
        except Exception as e:
            loading_label.destroy()
            messagebox.showerror("Search Error", f"An error occurred: {str(e)}")
            
    def _display_search_results(self, movies):
        if not movies:
            ttk.Label(self.results_frame.scrollable_frame, text="No results found").pack(pady=20)
            return
            
        # Create results grid
        results_grid = ttk.Frame(self.results_frame.scrollable_frame)
        results_grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure grid columns
        max_columns = 4
        for i in range(max_columns):
            results_grid.columnconfigure(i, weight=1)
            
        # Display movies in a grid layout
        for idx, movie in enumerate(movies[:20]):
            row, col = divmod(idx, max_columns)
            self._create_movie_card(results_grid, movie, row, col)
        
    def _create_movie_card(self, parent, movie, row, col):
        """Create a movie card with image, title, and details"""
        
        # Create frame with padding
        card = ttk.Frame(parent, style="Card.TFrame")
        card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")
        
        # Load movie poster
        poster_path = movie.get('poster_path')
        poster_image = self.image_cache.get_poster(poster_path) if poster_path else self.placeholder_image
        
        # Create and place poster image
        if poster_image:
            poster_label = ttk.Label(card, image=poster_image)
            poster_label.image = poster_image  # Keep a reference to prevent garbage collection
            poster_label.pack(pady=(10, 5))
            
            # Make poster clickable to view details
            poster_label.bind("<Button-1>", lambda e, m=movie: self._show_movie_details(m))
        
        # Movie title
        title_label = ttk.Label(card, text=movie.get('title', 'Untitled'), 
                               style="Title.TLabel", wraplength=160)
        title_label.pack(padx=5)
        title_label.bind("<Button-1>", lambda e, m=movie: self._show_movie_details(m))
        
        # Release year
        release_date = movie.get('release_date', '')
        if release_date:
            year = release_date.split('-')[0]
            ttk.Label(card, text=f"({year})", style="Year.TLabel").pack()
        
        # Rating
        rating = movie.get('vote_average', 0)
        ttk.Label(card, text=f"★ {rating:.1f}", style="Rating.TLabel").pack(pady=(2, 5))
        
        # Buttons frame
        btn_frame = ttk.Frame(card)
        btn_frame.pack(pady=(5, 10))
        
        # Details button
        details_btn = ttk.Button(btn_frame, text="Details", 
                                command=lambda m=movie: self._show_movie_details(m))
        details_btn.pack(side=tk.LEFT, padx=2)
        
        # Rate button
        rate_btn = ttk.Button(btn_frame, text="Rate", 
                              command=lambda m=movie: self._show_rating_dialog(m))
        rate_btn.pack(side=tk.LEFT, padx=2)
        
    def _show_movie_details(self, movie):
        """Show detailed information about a movie"""
        # Check cache first
        cached_details = self.db.get_cached_movie(movie['id'])
        
        if cached_details:
            self._display_movie_details(cached_details)
        else:
            # Fetch details from API
            try:
                details = self.tmdb.get_movie_details(movie['id'])
                # Cache the result
                self.db.cache_movie(movie['id'], details)
                self._display_movie_details(details)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load movie details: {str(e)}")
    
    def _display_movie_details(self, movie):
        """Display movie details in a new window"""
        details_window = tk.Toplevel(self)
        details_window.title(movie.get('title', 'Movie Details'))
        details_window.geometry("700x500")
        details_window.minsize(600, 400)
        
        # Main frame
        main_frame = ttk.Frame(details_window, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create two columns
        left_frame = ttk.Frame(main_frame)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Poster on the left
        poster_path = movie.get('poster_path')
        if poster_path:
            poster_image = self.image_cache.get_poster(poster_path, 'w342')
            if poster_image:
                poster_label = ttk.Label(left_frame, image=poster_image)
                poster_label.image = poster_image
                poster_label.pack(pady=10)
        
        # Movie information on the right
        ttk.Label(right_frame, text=movie.get('title', 'Untitled'), 
                 font=("Helvetica", 16, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        # Release date and runtime
        release_info = []
        
        if movie.get('release_date'):
            release_info.append(f"Released: {movie.get('release_date')}")
            
        if movie.get('runtime'):
            hours, minutes = divmod(movie.get('runtime'), 60)
            runtime_str = f"{hours}h {minutes}m" if hours else f"{minutes}m"
            release_info.append(f"Runtime: {runtime_str}")
            
        if release_info:
            ttk.Label(right_frame, text=" | ".join(release_info)).pack(anchor=tk.W, pady=(0, 10))
        
        # Genres
        if movie.get('genres'):
            genre_names = [genre['name'] for genre in movie.get('genres')]
            ttk.Label(right_frame, text="Genres: " + ", ".join(genre_names)).pack(anchor=tk.W, pady=(0, 10))
        
        # Rating
        rating = movie.get('vote_average', 0)
        ttk.Label(right_frame, text=f"Rating: ★ {rating:.1f} ({movie.get('vote_count', 0)} votes)", 
                 font=("Helvetica", 12, "bold"), foreground="#01b4e4").pack(anchor=tk.W, pady=(0, 15))
        
        # Overview
        ttk.Label(right_frame, text="Overview:", font=("Helvetica", 12, "bold")).pack(anchor=tk.W)
        overview_text = tk.Text(right_frame, wrap=tk.WORD, height=8, width=50)
        overview_text.insert(tk.END, movie.get('overview', 'No overview available.'))
        overview_text.config(state=tk.DISABLED)
        overview_text.pack(fill=tk.BOTH, expand=True, pady=(5, 15))
        
        # Cast
        if movie.get('credits', {}).get('cast'):
            cast = movie.get('credits', {}).get('cast')[:5]  # Top 5 cast members
            cast_names = [actor['name'] for actor in cast]
            ttk.Label(right_frame, text="Cast: " + ", ".join(cast_names)).pack(anchor=tk.W)
        
        # Action buttons
        btn_frame = ttk.Frame(right_frame)
        btn_frame.pack(pady=15, anchor=tk.W)
        
        # Rate button
        ttk.Button(btn_frame, text="Rate This Movie", 
                  command=lambda m=movie: self._show_rating_dialog(m)).pack(side=tk.LEFT, padx=(0, 10))
        
        # Get recommendations button
        ttk.Button(btn_frame, text="Similar Movies", 
                  command=lambda m=movie: self._show_similar_movies(m)).pack(side=tk.LEFT)
    
    def _show_rating_dialog(self, movie):
        """Show dialog for rating a movie"""
        rating_window = tk.Toplevel(self)
        rating_window.title(f"Rate: {movie.get('title')}")
        rating_window.geometry("300x150")
        rating_window.resizable(False, False)
        rating_window.transient(self)
        rating_window.grab_set()
        
        ttk.Label(rating_window, text=f"Rate '{movie.get('title')}':", 
                 font=("Helvetica", 12)).pack(pady=(15, 5))
        
        # Rating scale
        rating_var = tk.DoubleVar(value=5.0)
        rating_scale = ttk.Scale(rating_window, from_=0.5, to=10.0, 
                                orient=tk.HORIZONTAL, variable=rating_var, 
                                length=200)
        rating_scale.pack(pady=5)
        
        # Rating label
        rating_label = ttk.Label(rating_window, text="5.0")
        rating_label.pack()
        
        # Update label when scale value changes
        def update_rating_label(*args):
            rating_label.config(text=f"{rating_var.get():.1f}")
        
        rating_var.trace_add("write", update_rating_label)
        
        # Buttons frame
        btn_frame = ttk.Frame(rating_window)
        btn_frame.pack(pady=10, fill=tk.X)
        
        # Cancel button
        ttk.Button(btn_frame, text="Cancel", 
                  command=rating_window.destroy).pack(side=tk.LEFT, padx=(50, 10))
        
        # Submit button
        def submit_rating():
            rating = rating_var.get()
            self.db.save_user_rating(self.current_user_id, movie['id'], rating)
            messagebox.showinfo("Rating Saved", 
                              f"You rated '{movie.get('title')}' {rating:.1f}/10")
            rating_window.destroy()
            
            # Refresh recommendations if on that tab
            if self.notebook.index(self.notebook.select()) == 1:  # Recommendations tab
                self.load_recommendations()
        
        ttk.Button(btn_frame, text="Submit", 
                  command=submit_rating).pack(side=tk.LEFT)
    
    def _show_similar_movies(self, movie):
        """Show similar movies in the recommendations tab"""
        self.notebook.select(1)  # Switch to recommendations tab
        
        # Clear previous recommendations
        for widget in self.rec_container.scrollable_frame.winfo_children():
            widget.destroy()
            
        # Show loading indicator
        loading_label = ttk.Label(self.rec_container.scrollable_frame, 
                                text=f"Loading movies similar to '{movie.get('title')}'...")
        loading_label.pack(pady=20)
        self.update()
        
        try:
            # Get similar movies
            similar = self.tmdb.get_recommendations(movie['id'])
            similar_movies = similar.get('results', [])
            
            loading_label.destroy()
            
            # Display title
            ttk.Label(self.rec_container.scrollable_frame, 
                     text=f"Movies similar to '{movie.get('title')}'", 
                     font=("Helvetica", 14, "bold")).pack(pady=(0, 10))
            
            # Display results
            self._display_recommendations(similar_movies)
            
        except Exception as e:
            loading_label.destroy()
            messagebox.showerror("Error", f"Failed to load similar movies: {str(e)}")
    
    def load_recommendations(self):
        """Load personalized recommendations"""
        # Clear previous recommendations
        for widget in self.rec_container.scrollable_frame.winfo_children():
            widget.destroy()
            
        # Show loading indicator
        loading_label = ttk.Label(self.rec_container.scrollable_frame, text="Loading recommendations...")
        loading_label.pack(pady=20)
        self.update()
        
        try:
            # Get recommendations from engine
            recommendations = self.engine.generate_recommendations(self.current_user_id)
            
            loading_label.destroy()
            
            # Display results
            self._display_recommendations(recommendations)
            
        except Exception as e:
            loading_label.destroy()
            messagebox.showerror("Error", f"Failed to load recommendations: {str(e)}")
    
    def _display_recommendations(self, movies):
        """Display movie recommendations in a grid layout"""
        if not movies:
            ttk.Label(self.rec_container.scrollable_frame, 
                    text="No recommendations found. Try rating some movies first!").pack(pady=20)
            return
            
        # Create results grid
        results_grid = ttk.Frame(self.rec_container.scrollable_frame)
        results_grid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Configure grid columns
        max_columns = 4
        for i in range(max_columns):
            results_grid.columnconfigure(i, weight=1)
            
        # Display movies in a grid layout
        for idx, movie in enumerate(movies):
            row, col = divmod(idx, max_columns)
            self._create_movie_card(results_grid, movie, row, col)

if __name__ == "__main__":
    # Use environment variable in production
    API_KEY = os.getenv("TMDB_API_KEY", "")
    app = MovieRecommenderApp(API_KEY)
    app.mainloop()
