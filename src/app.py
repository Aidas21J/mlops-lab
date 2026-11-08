from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import os
from contextlib import asynccontextmanager
import mlflow.sklearn


MODEL_URI = os.getenv("MODEL_URI", "models:/sentiment-analyzer@champion")
state = { "model": None, "version": None }


@asynccontextmanager
async def lifespan(app: FastAPI):
    state["model"] = mlflow.sklearn.load_model(MODEL_URI)
    state["version"] = mlflow.MlflowClient().get_model_version_by_alias("sentiment-analyzer", "champion").version

    yield


app = FastAPI(title="Movie review sentiment analysis API", version="1.0", lifespan=lifespan)


class MessageRequest(BaseModel):
    message: str


@app.get("/ping")
def read_root():
    return { "status": "online" }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_version": state["version"] 
    }


@app.post("/predict")
def predict(payload: MessageRequest):
    model = state["model"]
    if model is None:
        raise HTTPException(status_code=500, detail="Model is not loaded.")
    
    X_input = [payload.message]
    prediction = model.predict(X_input)[0]

    return {
        "message": payload.message,
        "sentiment": "positive" if prediction == 1 else "negative",
        "confidence": float(model.predict_proba(X_input).max()),
    }
