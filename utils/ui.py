def get_css():
    return """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Rajdhani:wght@500;600;700&family=Inter:wght@400;600&display=swap');

    :root {
        --bg-color: #ffffff;
        --accent-primary: #00204a;
        --accent-secondary: #005792;
        --text-primary: #00204a;
    }

    .stApp {
        background-color: var(--bg-color);
        font-family: 'Inter', sans-serif;
        color: var(--text-primary);
    }

    h1, h2, h3, .title-font {
        font-family: 'Rajdhani', sans-serif !important;
        color: var(--accent-primary) !important;
    }

    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #d1d9e6;
    }

    /* Primary Buttons */
    div.stButton > button:first-child {
        background: var(--accent-primary);
        border: none;
        color: white !important;
        font-family: 'Rajdhani', sans-serif;
        font-weight: 700;
        letter-spacing: 1px;
        padding: 0.6rem;
        border-radius: 6px;
        width: 100%;
        transition: all 0.3s ease;
    }
    div.stButton > button:first-child:hover {
        background: var(--accent-secondary);
        transform: translateY(-2px);
    }

    /* HUD Header */
    .hud-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background: #ffffff;
        border-bottom: 2px solid var(--accent-primary);
        padding: 15px 25px;
        border-radius: 0 0 10px 10px;
        margin-bottom: 20px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05);
    }
    .hud-title {
        font-family: 'Rajdhani', sans-serif;
        font-size: 2.2rem;
        font-weight: 700;
        color: var(--accent-primary);
    }

    /* Cards */
    .glass-card {
        background: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 20px;
        border-radius: 12px;
        margin-bottom: 15px;
        box-shadow: 0 4px 10px rgba(0, 0, 0, 0.05);
    }
    .card-label {
        font-family: 'Rajdhani', sans-serif;
        color: var(--accent-primary);
        font-size: 1.1rem;
        font-weight: 700;
        text-transform: uppercase;
        border-bottom: 2px solid #f0f0f0;
        padding-bottom: 8px;
        margin-bottom: 12px;
    }
    .alert-card {
        background: #fff5f5;
        border: 1px solid #fc8181;
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 15px;
        margin-top: 15px;
    }
    .date-badge {
        background-color: #eef2f6;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85rem;
        font-weight: 600;
        color: #00204a;
        margin-top: 5px;
        display: inline-block;
    }
    </style>
    """
