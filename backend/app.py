"""AI-Based Sprint Planning Assistant - Flask entry point.   Run: python backend/app.py"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from flask import Flask
from models.features import ROOT

app = Flask(__name__, template_folder=str(ROOT / "frontend" / "templates"),
            static_folder=str(ROOT / "frontend" / "static"))


def bootstrap():
    if not (ROOT / "saved_models" / "risk_model.pkl").exists():
        from models.train_models import train_all
        train_all()
    import database
    database.init_db()
    from routes import pages, api
    app.register_blueprint(pages)
    app.register_blueprint(api)


bootstrap()

if __name__ == "__main__":
    app.run(debug=False, port=5000)
