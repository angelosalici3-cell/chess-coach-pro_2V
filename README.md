# chess-coach-pro_2V

## 1. Setup locale

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# compila secrets.toml
streamlit run app.py
