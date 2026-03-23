import os
import re
import random
import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

TMDB_API_KEY  = os.getenv("TMDB_API_KEY", "e09e05567aaecfcf274e1769075e9bf8")
TMDB_BASE     = "https://api.themoviedb.org/3"
TMDB_IMG      = "https://image.tmdb.org/t/p/w500"

# ── Mood config ───────────────────────────────────────────────
MOOD_CONFIG = {
    "happy":     {"genres": [35, 10751, 16],   "label": "Happy & Cheerful",     "emoji": "😊", "color": "#F59E0B"},
    "sad":       {"genres": [18, 10749],        "label": "Melancholic",          "emoji": "😢", "color": "#6366F1"},
    "excited":   {"genres": [28, 12, 878],      "label": "Excited & Pumped",     "emoji": "⚡", "color": "#EF4444"},
    "calm":      {"genres": [99, 36, 10402],    "label": "Calm & Reflective",    "emoji": "😌", "color": "#10B981"},
    "stressed":  {"genres": [35, 10751, 16],    "label": "Stressed & Anxious",   "emoji": "😰", "color": "#8B5CF6"},
    "bored":     {"genres": [12, 878, 9648],    "label": "Bored",                "emoji": "😑", "color": "#F97316"},
    "lonely":    {"genres": [10749, 18, 10751], "label": "Lonely",               "emoji": "🫂", "color": "#EC4899"},
    "romantic":  {"genres": [10749, 35],        "label": "Romantic",             "emoji": "💕", "color": "#F43F5E"},
    "angry":     {"genres": [28, 53, 80],       "label": "Angry",                "emoji": "😤", "color": "#DC2626"},
    "nostalgic": {"genres": [36, 10751, 10402], "label": "Nostalgic",            "emoji": "🌅", "color": "#D97706"},
    "curious":   {"genres": [99, 878, 9648],    "label": "Curious & Thoughtful", "emoji": "🤔", "color": "#0EA5E9"},
    "anxious":   {"genres": [35, 10751, 16],    "label": "Anxious",              "emoji": "😟", "color": "#7C3AED"},
}

# ── Keyword → mood mapping (no AI needed) ────────────────────
MOOD_KEYWORDS = {
    "happy":    ["happy", "joy", "joyful", "great", "amazing", "wonderful",
                 "fantastic", "good", "laugh", "fun", "excited", "cheerful",
                 "delighted", "glad", "pleased", "love", "awesome", "smile"],
    "sad":      ["sad", "cry", "depressed", "unhappy", "miserable", "grief",
                 "heartbreak", "broken", "down", "blue", "gloomy", "upset",
                 "disappointed", "lonely", "miss", "loss", "hurt", "pain"],
    "excited":  ["excited", "pumped", "hyped", "thrill", "adventure", "action",
                 "energy", "fire", "adrenaline", "rush", "electric", "wild"],
    "calm":     ["calm", "relax", "chill", "peaceful", "quiet", "slow",
                 "gentle", "easy", "serene", "tranquil", "meditate", "breathe",
                 "unwind", "rest", "cozy", "comfortable", "soft"],
    "stressed": ["stress", "stressed", "anxious", "overwhelmed", "pressure",
                 "tired", "exhausted", "drained", "burned", "burnout", "tense",
                 "worried", "nervous", "panic", "deadline", "busy", "work"],
    "bored":    ["bored", "boring", "nothing", "dull", "empty", "blank",
                 "uninterested", "meh", "whatever", "pointless", "lifeless"],
    "lonely":   ["lonely", "alone", "isolated", "nobody", "no one", "miss",
                 "empty", "disconnected", "abandoned", "forgotten"],
    "romantic": ["romantic", "love", "crush", "date", "relationship", "heart",
                 "affection", "tender", "intimate", "passion", "together"],
    "angry":    ["angry", "anger", "furious", "mad", "rage", "hate",
                 "annoyed", "frustrated", "irritated", "pissed", "fed up"],
    "nostalgic":["nostalgic", "nostalgia", "memory", "memories", "childhood",
                 "old", "miss", "past", "remember", "throwback", "classic"],
    "curious":  ["curious", "wonder", "interesting", "learn", "discover",
                 "mystery", "question", "explore", "think", "mind", "science"],
    "anxious":  ["anxious", "anxiety", "fear", "scared", "worried", "nervous",
                 "dread", "uneasy", "restless", "overthink", "panic"],
}


def detect_mood(text: str) -> dict:
    """
    Keyword-based mood detection — works without any API key.
    Scores each mood by counting keyword matches, picks the winner.
    """
    text_lower = text.lower()
    words      = re.findall(r'\w+', text_lower)
    scores     = {mood: 0 for mood in MOOD_KEYWORDS}

    for mood, keywords in MOOD_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:          # phrase match (catches "burned out")
                scores[mood] += 2
        for w in words:
            if w in keywords:             # single word match
                scores[mood] += 1

    best_mood  = max(scores, key=scores.get)
    best_score = scores[best_mood]

    # If nothing matched, default to calm
    if best_score == 0:
        best_mood = "calm"

    # Find second-best mood for nuance
    sorted_moods  = sorted(scores, key=scores.get, reverse=True)
    secondary     = sorted_moods[1] if scores[sorted_moods[1]] > 0 else None
    confidence    = min(0.95, 0.5 + (best_score * 0.08))

    nuances = {
        "happy":    "You're in a light and joyful headspace — perfect for fun films.",
        "sad":      "You're feeling emotional and reflective right now.",
        "excited":  "You're buzzing with energy and ready for action.",
        "calm":     "You're in a peaceful mood — ideal for slow, beautiful stories.",
        "stressed": "You need something easy to melt into and decompress.",
        "bored":    "You need something gripping to pull you out of the slump.",
        "lonely":   "You're craving warmth and human connection through story.",
        "romantic": "You're feeling tender and open-hearted.",
        "angry":    "You need an outlet — something intense and cathartic.",
        "nostalgic":"You're longing for something warm and familiar.",
        "curious":  "Your mind is open and ready to be challenged.",
        "anxious":  "Something comforting and easy will help you breathe.",
    }

    return {
        "mood":           best_mood,
        "confidence":     round(confidence, 2),
        "nuance":         nuances.get(best_mood, ""),
        "secondary_mood": secondary,
    }


# ── TMDB fetcher ──────────────────────────────────────────────
def get_tmdb_page(genre_ids: str, sort_by: str, page: int) -> list:
    url = (
        f"{TMDB_BASE}/discover/movie"
        f"?api_key={TMDB_API_KEY}"
        f"&with_genres={genre_ids}"
        f"&sort_by={sort_by}"
        f"&page={page}"
        f"&language=en-US"
        f"&include_adult=false"
    )
    try:
        r = requests.get(url, timeout=6)
        if r.ok:
            return r.json().get("results", [])
    except Exception as e:
        print(f"TMDB error: {e}")
    return []


def fetch_movies(mood: str, seen_ids: list) -> list:
    config    = MOOD_CONFIG[mood]
    genres    = config["genres"]
    seen_set  = set(seen_ids)

    # Use ONE genre at a time (rotating randomly) so results are different
    # across moods that share genres
    genre_id  = str(random.choice(genres))

    # 3 random pages from 3 different sort orders = ~60 movie pool
    pages     = random.sample(range(1, 20), 3)
    sorts     = ["popularity.desc", "vote_average.desc", "primary_release_date.desc"]
    random.shuffle(sorts)

    pool = []
    for i in range(3):
        pool += get_tmdb_page(genre_id, sorts[i], pages[i])

    # Also pull from a second genre for more variety
    if len(genres) > 1:
        genre2 = str(random.choice([g for g in genres if str(g) != genre_id]))
        pool  += get_tmdb_page(genre2, "popularity.desc", random.randint(1, 10))

    # Deduplicate pool
    seen_in_pool = set()
    unique = []
    for m in pool:
        if m["id"] not in seen_in_pool:
            seen_in_pool.add(m["id"])
            unique.append(m)

    # Shuffle entire pool — this is the key to variety
    random.shuffle(unique)

    movies = []
    for m in unique:
        if m["id"] in seen_set:       # skip already-seen
            continue
        if not m.get("poster_path"):  # skip no-poster
            continue
        if m.get("vote_average", 0) < 5.0:  # skip low quality
            continue

        movies.append({
            "id":         m["id"],
            "title":      m["title"],
            "overview":   m.get("overview", ""),
            "rating":     round(m.get("vote_average", 0), 1),
            "year":       (m.get("release_date") or "")[:4],
            "poster":     f"{TMDB_IMG}{m['poster_path']}",
            "tmdb_url":   f"https://www.themoviedb.org/movie/{m['id']}",
        })

        if len(movies) == 8:
            break

    return movies


def get_trailer(movie_id: int):
    url = f"{TMDB_BASE}/movie/{movie_id}/videos?api_key={TMDB_API_KEY}"
    try:
        r = requests.get(url, timeout=5)
        if r.ok:
            for v in r.json().get("results", []):
                if v.get("site") == "YouTube" and v.get("type") == "Trailer":
                    return v["key"]
    except Exception:
        pass
    return None


# ── Routes ────────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data      = request.get_json(silent=True) or {}
    user_text = (data.get("text") or "").strip()
    seen_ids  = data.get("seen_ids", [])

    if not user_text:
        return jsonify({"error": "Please enter how you are feeling."}), 400

    # Detect mood (no API key needed)
    mood_result = detect_mood(user_text)
    mood        = mood_result["mood"]
    config      = MOOD_CONFIG[mood]

    # Fetch movies
    movies = fetch_movies(mood, seen_ids)

    # Label picks
    if len(movies) > 0: movies[0]["pick_label"] = "Top Pick"
    if len(movies) > 2: movies[2]["pick_label"] = "Safe Bet"
    if len(movies) > 5: movies[5]["pick_label"] = "Unexpected Gem"

    return jsonify({
        "mood":           mood,
        "mood_label":     config["label"],
        "mood_emoji":     config["emoji"],
        "mood_color":     config["color"],
        "confidence":     mood_result["confidence"],
        "nuance":         mood_result["nuance"],
        "secondary_mood": mood_result["secondary_mood"],
        "movies":         movies,
        "seen_ids":       seen_ids + [m["id"] for m in movies],
    })


@app.route("/trailer/<int:movie_id>")
def trailer(movie_id):
    return jsonify({"trailer_key": get_trailer(movie_id)})


if __name__ == "__main__":
    app.run(debug=True)
