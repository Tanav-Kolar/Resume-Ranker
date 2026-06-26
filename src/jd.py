"""
Encoded knowledge about the target role: Senior AI Engineer, Founding Team @ Redrob AI.

All constants here are placeholders the human can tune without touching scoring logic.
The JD wants: production retrieval / ranking / search / recommendation at *product*
companies, 5-9 yrs, India-based. Non-technical roles and IT-services consultants are
anti-patterns the brief explicitly calls out.
"""

# ---------------------------------------------------------------------------
# Title tiers  (0.0 = clearly wrong role, 1.0 = ideal match)
# ---------------------------------------------------------------------------

# Patterns are matched case-insensitively against current_title and career titles.
# Order matters only for documentation; all patterns are checked.

TITLE_HIGH = [
    "machine learning",
    "ml engineer",
    "ai engineer",
    "nlp engineer",
    "search engineer",
    "recommendation",
    "ranking engineer",
    "retrieval",
    "applied scientist",
    "research engineer",
    "deep learning",
    "computer vision",
    "data scientist",          # borderline high — strong signal when paired with right skills
    "data engineer",           # strong pipeline signal
    "mlops",
    "platform engineer",
    "infrastructure engineer",
]

TITLE_MEDIUM = [
    "software engineer",
    "software developer",
    "backend engineer",
    "backend developer",
    "full stack",
    "fullstack",
    "python developer",
    "tech lead",
    "engineering lead",
    "principal engineer",
    "senior engineer",
    "analytics engineer",
    "bi engineer",
    "devops",
    "sre",
    "site reliability",
    "cloud engineer",
]

# Roles that are clearly non-technical or off-domain — push score toward zero.
# This is the primary anti-keyword-stuffer defence.
TITLE_LOW = [
    "hr ",
    "human resource",
    "recruiter",
    "talent acquisition",
    "accountant",
    "finance",
    "marketing",
    "sales",
    "business development",
    "content writer",
    "graphic designer",
    "ux designer",
    "ui designer",
    "product designer",
    "mechanical engineer",
    "civil engineer",
    "electrical engineer",
    "structural engineer",
    "chemical engineer",
    "supply chain",
    "logistics",
    "procurement",
    "operations manager",
    "customer support",
    "customer success",
    "project manager",         # generic PM — not eng PM
    "program manager",
    "scrum master",
    "business analyst",
    "legal",
    "compliance",
    "social media",
    "seo",
    "copywriter",
    "journalist",
    "teacher",
    "professor",
    "doctor",
    "nurse",
    "pharmacist",
]

# Scores assigned to each tier
TITLE_SCORE_HIGH = 1.0
TITLE_SCORE_MEDIUM = 0.55
TITLE_SCORE_LOW = 0.05
TITLE_SCORE_UNKNOWN = 0.30   # title not matched anywhere — default to medium-low

# ---------------------------------------------------------------------------
# Skill vocabulary
# ---------------------------------------------------------------------------
# Core ML/AI/Search skills relevant to the JD.  The human will tune these lists.

CORE_SKILLS = {
    # retrieval / search / ranking
    "information retrieval", "ir", "search", "ranking", "learning to rank",
    "ltr", "bm25", "elasticsearch", "solr", "opensearch", "lucene",
    "recommendation", "collaborative filtering", "matrix factorization",
    "two-tower", "ann", "approximate nearest neighbor", "faiss", "milvus",
    "pinecone", "weaviate", "qdrant", "vector search", "semantic search",
    # ml / deep learning
    "machine learning", "deep learning", "neural network", "pytorch", "tensorflow",
    "keras", "transformers", "hugging face", "bert", "gpt", "llm",
    "fine-tuning", "fine-tuning llms", "rlhf", "lora", "peft",
    "natural language processing", "nlp", "named entity recognition", "ner",
    "text classification", "question answering", "summarization",
    "speech recognition", "tts", "image classification", "object detection",
    "computer vision", "cv", "gans", "generative ai", "stable diffusion",
    # mlops / infra
    "mlflow", "kubeflow", "airflow", "prefect", "dagster",
    "feature store", "model serving", "triton", "torchserve", "bentoml",
    "ray", "spark", "kafka", "flink", "hadoop",
    # data / analytics
    "sql", "python", "pandas", "numpy", "scikit-learn", "sklearn",
    "xgboost", "lightgbm", "catboost", "a/b testing", "experimentation",
    "dbt", "data pipeline", "data engineering", "etl",
    "statistical modeling", "statistical analysis", "bayesian",
    # cloud / infra
    "aws", "gcp", "azure", "docker", "kubernetes", "k8s",
    "apache beam", "databricks",
}

# Skills that sound impressive but are generic tools — lower weight
GENERIC_SKILLS = {
    "excel", "powerpoint", "word", "outlook", "photoshop", "illustrator",
    "canva", "figma", "sketch", "tableau", "power bi", "looker",
    "salesforce", "jira", "confluence", "slack", "notion",
    "html", "css", "javascript", "react", "angular", "vue",
    "tailwind", "bootstrap", "jquery", "php", "wordpress",
}

# Proficiency multipliers for skill trust
PROFICIENCY_WEIGHT = {
    "expert": 1.0,
    "advanced": 0.85,
    "intermediate": 0.60,
    "beginner": 0.30,
}

# ---------------------------------------------------------------------------
# Experience band (years)
# ---------------------------------------------------------------------------
EXP_IDEAL_MIN = 5.0
EXP_IDEAL_MAX = 9.0
EXP_SWEET_MIN = 6.0   # extra reward for the sweet-spot 6-8 yrs
EXP_SWEET_MAX = 8.0

# ---------------------------------------------------------------------------
# Location fit scores
# ---------------------------------------------------------------------------
# The JD is India-based, no visa sponsorship outside India.

LOCATION_TIER = {
    # exact cities mentioned in JD or brief as highest-fit locations
    "noida": 1.0,
    "pune": 1.0,
    # Tier-1 Indian cities
    "bengaluru": 0.90,
    "bangalore": 0.90,
    "mumbai": 0.90,
    "hyderabad": 0.90,
    "delhi": 0.90,
    "new delhi": 0.90,
    "ncr": 0.90,
    "gurgaon": 0.90,
    "gurugram": 0.90,
    "chennai": 0.85,
    "kolkata": 0.85,
    "ahmedabad": 0.80,
    "jaipur": 0.80,
    "kochi": 0.75,
    "chandigarh": 0.75,
    # generic India match — will be caught by country == "India"
}

LOCATION_SCORE_INDIA_GENERIC = 0.70       # India, city not in tier list
LOCATION_SCORE_ABROAD_WILLING = 0.40     # outside India but willing to relocate
LOCATION_SCORE_ABROAD_NOT_WILLING = 0.05 # outside India, not willing to relocate

# ---------------------------------------------------------------------------
# Company-type hints (product vs services)
# ---------------------------------------------------------------------------
# Industry strings suggesting IT services / outsourcing (moderate negative signal)
SERVICES_INDUSTRIES = {
    "it services", "information technology and services",
    "outsourcing", "bpo", "kpo", "staffing", "consulting",
}
