# 🩺 Infirmière à Domicile — image Docker
#
# Construction :
#   docker build -t nurse-planner .
#
# Lancement (base de données persistée dans le volume ./data) :
#   docker run -d --name nurse-planner -p 8501:8501 -v nurse_data:/data nurse-planner
#
# La base SQLite et le mot de passe sont conservés dans /data (volume).

FROM python:3.12-slim

# Ne pas convertir les warnings en erreurs, ni tamponner la sortie
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dépendances d'abord (cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code de l'application
COPY app.py database.py auth.py manifest.json ./
COPY icons/ ./icons/
COPY README.md .

# Utilisateur non-root (recommandé pour les données de santé)
RUN useradd --create-home appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data
USER appuser

# La base de données vit dans /data (volume recommandé)
ENV NURSE_DATA_DIR=/data

EXPOSE 8501

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=4)" || exit 1

CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501", \
     "--server.headless=true", \
     "--browser.gatherUsageStats=false"]
