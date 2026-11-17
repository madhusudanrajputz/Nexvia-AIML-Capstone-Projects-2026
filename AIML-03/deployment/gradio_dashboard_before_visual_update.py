
import html
import requests
import gradio as gr

API_URL = "http://127.0.0.1:8000"

CSS = """
.gradio-container {
    max-width: 1250px !important;
    margin: auto !important;
}
.hero {
    background: linear-gradient(120deg, #101827, #1d344e);
    border: 1px solid #32465d;
    border-radius: 18px;
    padding: 28px;
    margin-bottom: 20px;
}
.hero h1 {
    color: #ffffff;
    font-size: 34px;
    margin-bottom: 10px;
}
.hero p { color: #d5dfeb; }
.movie-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(225px, 1fr));
    gap: 15px;
    margin-top: 15px;
}
.movie-card {
    background: #172235;
    color: #ffffff;
    border: 1px solid #334155;
    border-radius: 14px;
    padding: 18px;
    min-height: 155px;
}
.movie-card h3 {
    color: #ffffff;
    font-size: 17px;
    margin: 8px 0;
}
.movie-card .genre {
    color: #b7c9dc;
    font-size: 13px;
}
.movie-card .score {
    color: #88e0bc;
    font-size: 13px;
    margin-top: 12px;
}
.movie-number {
    color: #93c5fd;
    font-size: 12px;
    font-weight: bold;
}
.section-panel {
    padding: 20px;
    border-radius: 14px;
    border: 1px solid #334155;
    background: #172235;
    color: #ffffff;
}
.section-panel h3 { color: #ffffff; }
.section-panel p { color: #d5dfeb; }
"""

def request_api(endpoint, payload):
    response = requests.post(
        API_URL + endpoint,
        json=payload,
        timeout=90
    )
    response.raise_for_status()
    return response.json()

def create_movie_cards(movies):
    if not movies:
        return "<p>No recommendations returned.</p>"

    cards = ['<div class="movie-grid">']

    for index, movie in enumerate(movies, 1):
        title = html.escape(str(movie.get("title", "Unknown movie")))
        genres = html.escape(str(movie.get("genres", "Unknown")))
        score = movie.get("ranking_score")

        if score is None:
            score_text = "Ranking score: Not applicable"
        else:
            score_text = f"Ranking score: {float(score):.4f}"

        cards.append(f"""
        <div class="movie-card">
            <div class="movie-number">RECOMMENDATION #{index}</div>
            <h3>{title}</h3>
            <div class="genre">{genres.replace('|', ' · ')}</div>
            <div class="score">{score_text}</div>
        </div>
        """)

    cards.append("</div>")
    return "\n".join(cards)

def recommendation_response(endpoint, payload):
    try:
        data = request_api(endpoint, payload)

        movies = data.get("recommendations", [])
        count = len(movies)

        cache_status = data.get("cache_status", "Not applicable")
        recommendation_type = data.get("recommendation_type")

        summary = (
            f"**{count} recommendations generated**  \n"
            f"**Cache status:** {cache_status}"
        )

        if recommendation_type:
            summary += f"  \n**Type:** {recommendation_type}"

        return summary, create_movie_cards(movies)

    except Exception as error:
        return (
            f"**Request failed:** {str(error)}",
            "<p>Could not load recommendations.</p>"
        )

def personalized(user_id, top_k):
    try:
        user_id = int(user_id)
        if user_id < 1:
            raise ValueError("User ID must be positive.")
    except (TypeError, ValueError):
        return "Enter a valid positive integer User ID.", ""

    return recommendation_response(
        "/recommend",
        {
            "user_id": user_id,
            "top_k": int(top_k),
            "preferred_genres": None
        }
    )

def cold_start(top_k):
    return recommendation_response(
        "/recommend",
        {
            "user_id": None,
            "top_k": int(top_k),
            "preferred_genres": None
        }
    )

def genre_based(genres, top_k):
    if not genres:
        return "Select at least one genre.", ""

    return recommendation_response(
        "/recommend/new-items",
        {
            "preferred_genres": genres,
            "top_k": int(top_k)
        }
    )

def health_status():
    try:
        response = requests.get(API_URL + "/health", timeout=10)
        response.raise_for_status()
        info = response.json()

        return (
            f"**API:** {info.get('status', 'unknown')}  \n"
            f"**Model loaded:** {info.get('model_loaded')}  \n"
            f"**Redis connected:** {info.get('redis_connected')}"
        )
    except Exception as error:
        return f"**Backend unavailable:** {error}"

with gr.Blocks(
    title="AIML-03 Movie Recommendation Engine",
    css=CSS
) as demo:

    gr.HTML("""
    <div class="hero">
        <h1>Movie Recommendation Engine</h1>
        <p>
            AIML-03 | Nexvia Internship Project
        </p>
        <p>
            Two-Tower Retrieval · FAISS · Wide & Deep Ranking
            · FastAPI · Redis
        </p>
    </div>
    """)

    with gr.Row():
        health = gr.Markdown(value=health_status())
        refresh = gr.Button("Refresh System Status", scale=0)

    refresh.click(
        fn=health_status,
        outputs=health
    )

    with gr.Tabs():

        with gr.Tab("Personalized Recommendations"):
            gr.Markdown(
                "### Discover movies for an existing user"
            )

            with gr.Row():
                user_id = gr.Number(
                    value=100,
                    precision=0,
                    label="MovieLens User ID"
                )
                personalized_count = gr.Slider(
                    1, 20, value=10, step=1,
                    label="Number of recommendations"
                )

            personalized_button = gr.Button(
                "Generate Personalized Recommendations",
                variant="primary"
            )

            personalized_summary = gr.Markdown()
            personalized_cards = gr.HTML()

            personalized_button.click(
                fn=personalized,
                inputs=[user_id, personalized_count],
                outputs=[
                    personalized_summary,
                    personalized_cards
                ]
            )

        with gr.Tab("Cold-Start Recommendations"):
            gr.Markdown(
                "### Recommendations for a new user"
            )
            gr.Markdown(
                "No user history is available. "
                "The system uses its popularity-based fallback."
            )

            cold_count = gr.Slider(
                1, 20, value=10, step=1,
                label="Number of recommendations"
            )
            cold_button = gr.Button(
                "Generate Cold-Start Recommendations",
                variant="primary"
            )

            cold_summary = gr.Markdown()
            cold_cards = gr.HTML()

            cold_button.click(
                fn=cold_start,
                inputs=[cold_count],
                outputs=[cold_summary, cold_cards]
            )

        with gr.Tab("Genre-Based Recommendations"):
            gr.Markdown(
                "### Explore movies by preferred genres"
            )

            genres = gr.CheckboxGroup(
                choices=[
                    "Action", "Adventure", "Animation",
                    "Children", "Comedy", "Crime",
                    "Documentary", "Drama", "Fantasy",
                    "Film-Noir", "Horror", "Mystery",
                    "Romance", "Sci-Fi", "Thriller",
                    "War", "Western"
                ],
                value=["Sci-Fi", "Adventure"],
                label="Preferred genres"
            )

            genre_count = gr.Slider(
                1, 20, value=10, step=1,
                label="Number of recommendations"
            )

            genre_button = gr.Button(
                "Find Movies by Genre",
                variant="primary"
            )

            genre_summary = gr.Markdown()
            genre_cards = gr.HTML()

            genre_button.click(
                fn=genre_based,
                inputs=[genres, genre_count],
                outputs=[genre_summary, genre_cards]
            )

        with gr.Tab("Architecture"):
            gr.Markdown("""
### How the Recommendation Engine Works

**Step 1 — Data Preparation**

MovieLens 25M ratings are cleaned and split chronologically.
Apache Spark is used for feature preparation.

**Step 2 — Candidate Retrieval**

TensorFlow Recommenders Two-Tower models generate
user and movie embeddings.

**Step 3 — Fast Similarity Search**

FAISS retrieves candidate movies using the saved embedding index.

**Step 4 — Deep Ranking**

A Wide & Deep model scores candidates and produces
the final ranking.

**Step 5 — Serving**

FastAPI serves recommendations, while Redis caches
eligible repeated requests.

**Cold-start support:** Popularity-based and
genre-based fallback methods.
""")

        with gr.Tab("Model Evaluation"):
            gr.Markdown("""
### Offline Evaluation Results

The following results come from the saved
55-user matched evaluation.

| Metric | Popularity Baseline | Two-Stage Model |
|---|---:|---:|
| Recall@10 | 0.044186 | 0.024384 |
| NDCG@10 | 0.077582 | 0.041228 |

**Interpretation:** The popularity baseline performed
better than the current two-stage model on this
limited evaluation subset.

**Limitations:** Neural models were trained on sampled
interactions, not the complete 25M ratings.
Live Triton serving and a genuine online A/B test
have not yet been verified.

These ranking scores and offline metrics do not
represent measured online click-through rates.
""")

    gr.Markdown(
        "---\n"
        "**AIML-03 | Two-Stage Personalized Recommendation Engine**"
    )

if __name__ == "__main__":
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True
    )
