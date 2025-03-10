# Movie Recommender Project Documentation

## 1. Introduction

This document provides detailed information about the Movie Recommender application, which delivers personalized movie recommendations utilizing The Movie Database (TMDb) API. This application is designed to offer recommendations tailored to user preferences, with support for multiple languages and an integrated user rating system.

## 2. Features

-   **Multi-language Movie Searching**: Allows users to search for movies in various languages, enhancing accessibility and relevance.
-   **Personalized Recommendations**: Leverages user ratings and preferences to suggest movies that align with their tastes.
-   **User Rating System**: Enables users to rate movies, which helps refine future recommendations.
-   **International Movie Database**: Supports an extensive database of movies from around the globe, providing a wide variety of options.
-   **User Authentication**: Secure user login and signup functionality.
-   **Genre-Based Recommendations**: Delivers recommendations based on user-defined favorite genres.
-   **Mood-Based Recommendations**: Suggests movies based on the user's current mood, enhancing personalization.

## 3. Architecture

The application is structured into several key components:

-   **Graphical User Interface (GUI)**: Built with Tkinter, providing an interactive user experience.
-   **MovieDataFetcher**: Handles fetching movie data from the TMDb API, including search, details, and image retrieval.
-   **MovieDatabaseManager**: Manages database operations, including storing and retrieving user ratings and movie details.
-   **RecommendationEngine**: Generates movie recommendations based on user ratings, preferences, and movie attributes.

## 4. Modules

### 4.1. MovieDataFetcher

This module is responsible for interacting with the TMDb API.

-   **Key Components**:
    -   `__init__`: Initializes the API key and configures the session with retry mechanisms.
    -   `load_genres`: Loads movie genres from the TMDb API to provide genre-specific recommendations.
    -   `search_movies`: Searches for movies based on a query string, language, and region.
    -   `get_movie_details`: Retrieves detailed information about a specific movie.
    -   `get_discover_movies`: Discovers movies by genre IDs, language, and region.
    -   `fetch_image`: Fetches movie posters from TMDb.

-   **API Usage**:
    -   Utilizes the TMDb API to fetch movie data. Requires a valid API key, which should be stored securely using environment variables.

### 4.2. MovieDatabaseManager

This module manages all database operations.

-   **Key Components**:
    -   `__init__`: Initializes the database connection and sets up the database schema.
    -   `initialize_database`: Creates the necessary tables for storing user data, movie data, and user ratings.
    -   `get_user_preferences`: Retrieves user-specific preferences, such as language and region.
    -   `set_user_preferences`: Updates user preferences in the database.
    -   `save_user_rating`: Saves user ratings for movies.
    -   `get_user_ratings`: Retrieves all ratings submitted by a user.
    -   `save_movie`: Saves movie data into the database.
    -   `get_movie_details`: Retrieves detailed information about a specific movie from the database.
    -   `get_rated_movies_with_details`: Retrieves all movies rated by a user, along with their details.
    -   `determine_user_favorite_genres`: Determines the user’s favorite genres based on their ratings.
    -   `create_user`: Creates a new user in the database.
    -   `authenticate_user`: Verifies user credentials against the database.

-   **Database Schema**:
    -   `users`: Stores user information (user_id, username, password_hash, created_at).
    -   `movies`: Stores movie details (movie_id, title, original_title, original_language, release_year, plot_summary, poster_path, popularity_score, average_vote, production_region, genres).
    -   `user_ratings`: Stores user ratings for movies (user_id, movie_id, rating, timestamp).
    -   `user_preferences`: Stores user preferences (user_id, language, region).

### 4.3. RecommendationEngine

This module generates movie recommendations.

-   **Key Components**:
    -   `__init__`: Initializes the recommendation engine with the movie database and fetcher.
    -   `_calculate_hybrid_score`: Calculates a hybrid score using collaborative and content-based filtering to rank movies.
    -   `recommend_movies_based_on_mood`: Recommends movies based on the user's mood by mapping moods to relevant genres.

-   **Recommendation Strategy**:
    -   Utilizes a combination of collaborative filtering (user ratings) and content-based filtering (movie genres and attributes) to generate personalized recommendations.

### 4.4. GUI (Tkinter)

The GUI provides an interactive interface for users to interact with the application.

-   **Key Windows**:
    -   **Login Window**: Manages user login and signup functionalities.
    -   **Main Application Window**: Displays search results, movie details, recommendations, and user preferences.

-   **User Interface Components**:
    -   Search bar for finding movies.
    -   Movie display area with posters and details.
    -   User rating input.
    -   Preference settings (language, region).
    -   Recommendation display.

## 5. Setup and Installation

### 5.1. Prerequisites

-   Python 3.6+
-   pip

### 5.2. Installation Steps

1.  Clone the repository:

    ```
    git clone [repository URL]
    ```

2.  Navigate to the project directory:

    ```
    cd movie_recommender
    ```

3.  Create a virtual environment:

    ```
    python3 -m venv venv
    ```

4.  Activate the virtual environment:

    -   On macOS/Linux:

        ```
        source venv/bin/activate
        ```

    -   On Windows:

        ```
        venv\Scripts\activate
        ```

5.  Install the required packages:

    ```
    pip install -r requirements.txt
    ```

6.  Set up the `.env` file:

    -   Create a `.env` file in the project root directory.
    -   Add your TMDb API key:

        ```
        TMDB_API_KEY=YOUR_TMDB_API_KEY
        ```

        Replace `YOUR_TMDB_API_KEY` with your actual TMDb API key.

### 5.3. Running the Application

python movie_rec.py

## 6. Usage

1.  **Login/Signup**:
    -   If you are a new user, sign up by providing a username and password.
    -   If you have an existing account, log in with your credentials.
2.  **Searching for Movies**:
    -   Use the search bar to find movies by title.
    -   Select a movie from the search results to view its details.
3.  **Rating Movies**:
    -   Rate movies to improve the accuracy of your recommendations.
4.  **Setting Preferences**:
    -   Adjust your language and region preferences to customize your movie selections.
5.  **Getting Recommendations**:
    -   View personalized movie recommendations based on your ratings and preferences.

## 7. Contributing

Contributions to this project are welcome. Please follow these steps:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Commit your changes with clear, descriptive commit messages.
4.  Submit a pull request.

## 8. License

This project is licensed under the MIT License. See the `LICENSE` file for details.

## 9. Future Enhancements

-   **Advanced Recommendation Algorithms**: Implement more sophisticated recommendation algorithms, such as matrix factorization or deep learning models.
-   **Improved GUI**: Enhance the user interface with more intuitive controls and better visual appeal.
-   **Expanded Mood-Based Recommendations**: Add more moods and fine-tune the genre mappings.
-   **Cloud Deployment**: Deploy the application to a cloud platform for broader accessibility.
