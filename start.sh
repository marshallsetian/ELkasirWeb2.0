export FLASK_APP=app.py
export FLASK_ENV=${FLASK_ENV:-production}
flask run --host=0.0.0.0 --port=$PORT
