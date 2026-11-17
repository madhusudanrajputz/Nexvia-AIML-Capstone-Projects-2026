
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
    from fastapi import Request
    import app as backend

    if not hasattr(backend.app.state, "engine"):
        raise RuntimeError("Recommendation engine not initialized")

    request = Request({
        "type": "http",
        "method": "POST",
        "path": endpoint,
        "headers": [],
        "query_string": b"",
        "app": backend.app,
    })

    if endpoint == "/recommend":
        validated = backend.RecommendationRequest(**payload)
        return backend.recommend(validated, request)

    if endpoint == "/recommend/new-items":
        validated = backend.NewItemRequest(**payload)
        return backend.recommend_new_items_api(validated, request)

    raise ValueError(f"Unsupported endpoint: {endpoint}")


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
    import app as backend

    loaded = hasattr(backend.app.state, "engine")
    cache = getattr(backend.app.state, "redis", None)

    return (
        f"**API:** {'ok' if loaded else 'not ready'}  \\n"
        f"**Model loaded:** {loaded}  \\n"
        f"**Redis connected:** {cache is not None}"
    )


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
            gr.HTML('\n        <div style="padding:20px;background:#131e30;\n                    border:1px solid #334155;border-radius:16px;\n                    color:white">\n\n          <h2 style="color:white">Two-Stage Recommendation Architecture</h2>\n\n          <div style="display:flex;flex-wrap:wrap;\n                      justify-content:center;gap:12px;\n                      align-items:center;margin-top:24px">\n\n            <div style="padding:18px;background:#24364f;border-radius:12px">\n              MovieLens 25M<br><small>Chronological split + Spark</small>\n            </div>\n\n            <div style="font-size:25px">→</div>\n\n            <div style="padding:18px;background:#24364f;border-radius:12px">\n              Two-Tower Model<br><small>User and movie embeddings</small>\n            </div>\n\n            <div style="font-size:25px">→</div>\n\n            <div style="padding:18px;background:#24364f;border-radius:12px">\n              FAISS<br><small>Candidate retrieval</small>\n            </div>\n\n            <div style="font-size:25px">→</div>\n\n            <div style="padding:18px;background:#24364f;border-radius:12px">\n              Wide &amp; Deep<br><small>Candidate ranking</small>\n            </div>\n\n            <div style="font-size:25px">→</div>\n\n            <div style="padding:18px;background:#205449;border-radius:12px">\n              FastAPI + Redis<br><small>Serving and caching</small>\n            </div>\n\n            <div style="font-size:25px">→</div>\n\n            <div style="padding:18px;background:#205449;border-radius:12px">\n              Gradio Dashboard<br><small>Movie recommendations</small>\n            </div>\n          </div>\n\n          <p style="color:#cbd5e1;margin-top:24px">\n            Offline training creates model artifacts and the FAISS index.\n            During inference, saved embeddings and ranking models are used\n            to retrieve and rank candidate movies.\n            Cold-start requests use popularity or genre-based fallbacks.\n          </p>\n        </div>\n')

        with gr.Tab("Model Evaluation"):
            gr.HTML('\n        <div style="padding:22px;background:#131e30;\n                    border:1px solid #334155;border-radius:16px;\n                    color:white">\n\n          <h2 style="color:white">Offline Model Evaluation</h2>\n          <p style="color:#cbd5e1">\n            Matched evaluation on 55 warm-start users.\n            Higher scores are better.\n          </p>\n\n          <h3 style="color:white">Recall@10</h3>\n\n          <p style="margin-bottom:4px">Popularity Baseline — 0.044186</p>\n          <div style="background:#334155;border-radius:8px">\n            <div style="width:88.37%;height:20px;background:#4ade80;\n                        border-radius:8px"></div>\n          </div>\n\n          <p style="margin:14px 0 4px">Two-Stage Model — 0.024384</p>\n          <div style="background:#334155;border-radius:8px">\n            <div style="width:48.77%;height:20px;background:#60a5fa;\n                        border-radius:8px"></div>\n          </div>\n\n          <h3 style="color:white;margin-top:30px">NDCG@10</h3>\n\n          <p style="margin-bottom:4px">Popularity Baseline — 0.077582</p>\n          <div style="background:#334155;border-radius:8px">\n            <div style="width:96.98%;height:20px;background:#4ade80;\n                        border-radius:8px"></div>\n          </div>\n\n          <p style="margin:14px 0 4px">Two-Stage Model — 0.041228</p>\n          <div style="background:#334155;border-radius:8px">\n            <div style="width:51.54%;height:20px;background:#60a5fa;\n                        border-radius:8px"></div>\n          </div>\n\n          <p style="color:#cbd5e1;margin-top:25px">\n            <strong>Interpretation:</strong> The popularity baseline\n            outperformed the current two-stage model on this evaluation\n            sample. More training data, model tuning and improved\n            candidate retrieval are potential next steps.\n          </p>\n\n          <p style="color:#cbd5e1">\n            <strong>Limitations:</strong> Neural models were trained on\n            sampled interactions. Live Triton serving and a genuine\n            online A/B experiment have not been completed.\n            No real CTR is reported.\n          </p>\n        </div>\n')

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
