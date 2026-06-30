"""Shared fixtures for the pipeline test suite."""
import pytest


@pytest.fixture
def candidate_ai_engineer():
    """Clean, strong ML candidate — should score high."""
    return {
        "candidate_id": "CAND_0000001",
        "profile": {
            "current_title": "ML Engineer",
            "years_of_experience": 7,
            "location": "Bangalore",
            "country": "India",
        },
        "career_history": [
            {
                "company": "Flipkart",
                "title": "ML Engineer",
                "start_date": "2019-01-01",
                "end_date": "2024-01-01",
                "duration_months": 60,
                "is_current": False,
            }
        ],
        "skills": [
            {"name": "machine learning", "proficiency": "expert", "duration_months": 72, "endorsements": 12},
            {"name": "pytorch", "proficiency": "advanced", "duration_months": 48, "endorsements": 5},
            {"name": "python", "proficiency": "expert", "duration_months": 84, "endorsements": 20},
            {"name": "deep learning", "proficiency": "advanced", "duration_months": 36, "endorsements": 8},
            {"name": "sql", "proficiency": "intermediate", "duration_months": 60, "endorsements": 3},
        ],
        "education": [
            {
                "institution": "IIT Delhi",
                "degree": "B.Tech",
                "field_of_study": "Computer Science",
                "start_year": 2012,
                "end_year": 2016,
                "tier": "tier1",
            }
        ],
        "redrob_signals": {
            "last_active_date": "2026-06-20",
            "open_to_work_flag": True,
            "recruiter_response_rate": 0.8,
            "willing_to_relocate": False,
            "skill_assessment_scores": {"machine learning": 88, "pytorch": 75},
        },
    }


@pytest.fixture
def candidate_hr():
    """Clearly off-domain HR candidate — should score very low."""
    return {
        "candidate_id": "CAND_0000002",
        "profile": {
            "current_title": "HR Manager",
            "years_of_experience": 5,
            "location": "Mumbai",
            "country": "India",
        },
        "career_history": [
            {
                "company": "Some Corp",
                "title": "HR Manager",
                "start_date": "2019-01-01",
                "end_date": "2024-01-01",
                "duration_months": 60,
                "is_current": False,
            }
        ],
        "skills": [],
        "education": [],
        "redrob_signals": {
            "open_to_work_flag": None,
            "recruiter_response_rate": -1,
            "willing_to_relocate": False,
        },
    }


@pytest.fixture
def candidate_consulting_only():
    """All jobs at IT consulting firms — should be filtered out."""
    return {
        "candidate_id": "CAND_0000003",
        "profile": {
            "current_title": "Software Engineer",
            "years_of_experience": 5,
            "location": "Chennai",
            "country": "India",
        },
        "career_history": [
            {"company": "Infosys", "title": "SE", "start_date": "2019-01-01", "duration_months": 30},
            {"company": "TCS", "title": "SE", "start_date": "2021-07-01", "duration_months": 30},
        ],
        "skills": [],
        "education": [],
        "redrob_signals": {},
    }


@pytest.fixture
def candidate_fictional():
    """Career history contains a fictional company — should be filtered out."""
    return {
        "candidate_id": "CAND_0000004",
        "profile": {
            "current_title": "Software Engineer",
            "years_of_experience": 3,
            "location": "Delhi",
            "country": "India",
        },
        "career_history": [
            {"company": "Pied Piper", "title": "Engineer", "start_date": "2021-01-01", "duration_months": 24},
        ],
        "skills": [],
        "education": [],
        "redrob_signals": {},
    }


@pytest.fixture
def candidate_honeypot():
    """Impossible profile: career tenure far exceeds stated YoE."""
    return {
        "candidate_id": "CAND_0000005",
        "profile": {
            "current_title": "ML Engineer",
            "years_of_experience": 5,
            "location": "Pune",
            "country": "India",
        },
        "career_history": [
            {
                "company": "StartupA",
                "title": "ML Engineer",
                "start_date": "2010-01-01",
                "end_date": "2020-01-01",
                "duration_months": 144,  # 12 yrs of months >> 5 yrs stated
            }
        ],
        "skills": [],
        "education": [],
        "redrob_signals": {},
    }


@pytest.fixture
def candidate_zero_dur_honeypot():
    """Honeypot: ≥4 skills marked advanced/expert with zero duration_months."""
    return {
        "candidate_id": "CAND_0000006",
        "profile": {"current_title": "ML Engineer", "years_of_experience": 3},
        "career_history": [
            {"company": "TechCo", "title": "Engineer", "start_date": "2021-01-01", "duration_months": 36}
        ],
        "skills": [
            {"name": "pytorch", "proficiency": "expert", "duration_months": 0},
            {"name": "tensorflow", "proficiency": "expert", "duration_months": 0},
            {"name": "machine learning", "proficiency": "advanced", "duration_months": 0},
            {"name": "deep learning", "proficiency": "expert", "duration_months": 0},
        ],
        "education": [],
        "redrob_signals": {},
    }


@pytest.fixture
def minimal_candidate():
    """Bare-minimum valid candidate dict — useful for testing defaults."""
    return {
        "candidate_id": "CAND_9999999",
        "profile": {},
        "career_history": [],
        "skills": [],
        "education": [],
        "redrob_signals": {},
    }
