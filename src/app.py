from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import joblib
import os
from contextlib import asynccontextmanager

model = None
MODEL_PATH = "models/model.pkl"

@asynccontextmanager
async def lifespan(app: FastAPI):
    global model
    if os.path.exists(MODEL_PATH):
        model = joblib.load(MODEL_PATH)
    else:
        print(f"Warning: model file ({MODEL_PATH}) was not found.")
    
    yield
    
    model = None
    print("Shutting down...")

app = FastAPI(title="Movie review sentiment analysis API", version="1.0", lifespan=lifespan)


class MessageRequest(BaseModel):
    message: str


@app.get("/ping")
def read_root():
    return { "status": "online" }


@app.post("/predict")
def predict(payload: MessageRequest):
    global model
    if model is None:
        raise HTTPException(status_code=500, detail="Model is not loaded.")
    
    X_input = [payload.message]
    prediction = model.predict(X_input)[0]

    return {
        "message": payload.message,
        "sentiment": "positive" if prediction == 1 else "negative",
        "confidence": float(model.predict_proba(X_input).max()),
    }
