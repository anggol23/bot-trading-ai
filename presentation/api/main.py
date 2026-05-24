from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
import jwt
import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from presentation.api.database import (
    get_portfolio_summary,
    get_active_positions,
    get_recent_signals,
    get_volume_anomalies,
    get_equity_curve,
    get_latest_candles,
    get_trade_history,
    get_daily_target_status,
    create_user,
    get_user_by_email,
    update_user_keys,
    get_user_keys,
)
from presentation.api.models import (
    PortfolioSummaryResponse,
    PositionResponse,
    SignalResponse,
    VolumeAnomalyResponse,
    ChartDataPoint,
    CandleResponse,
    TradeHistoryResponse,
    DailyTargetResponse,
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserKeysRequest,
    UserKeysResponse,
)

app = FastAPI(
    title="AI Trading Agent Dashboard API",
    description="Backend API for the AI Trading Web Dashboard with Multi-user support",
    version="2.0.0"
)

# Enable CORS for React Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# JWT & Passlib configurations
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-key-123456789-abcdef")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # 7 days

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau kedaluwarsa. Silakan login kembali.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id: int = payload.get("user_id")
        email: str = payload.get("email")
        if user_id is None or email is None:
            raise credentials_exception
        return {"id": user_id, "email": email}
    except jwt.PyJWTError:
        raise credentials_exception

# ──────────────────────────────── Auth Endpoints ────────────────────────────────

@app.post("/api/auth/register", response_model=TokenResponse)
def api_register(request: UserRegisterRequest):
    existing_user = get_user_by_email(request.email)
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email sudah terdaftar")
    
    hashed = hash_password(request.password)
    try:
        user_id = create_user(request.email, hashed)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal membuat akun: {str(e)}")
    
    access_token = create_access_token(data={"user_id": user_id, "email": request.email})
    return TokenResponse(
        access_token=access_token,
        email=request.email,
        user_id=user_id
    )

@app.post("/api/auth/login", response_model=TokenResponse)
def api_login(request: UserLoginRequest):
    user = get_user_by_email(request.email)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email atau password salah")
    if not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email atau password salah")
    
    access_token = create_access_token(data={"user_id": user["id"], "email": user["email"]})
    return TokenResponse(
        access_token=access_token,
        email=user["email"],
        user_id=user["id"]
    )

@app.get("/api/auth/keys", response_model=UserKeysResponse)
def api_get_keys(current_user: dict = Depends(get_current_user)):
    keys = get_user_keys(current_user["id"])
    if not keys:
        return UserKeysResponse(api_key=None, api_secret=None)
    
    # Mask API key and secret for security
    api_key_masked = None
    if keys.get("api_key"):
        k = keys["api_key"]
        api_key_masked = k[:4] + "*" * (len(k) - 8) + k[-4:] if len(k) > 8 else "****"
    
    api_secret_masked = None
    if keys.get("api_secret"):
        s = keys["api_secret"]
        api_secret_masked = s[:4] + "*" * (len(s) - 8) + s[-4:] if len(s) > 8 else "****"

    return UserKeysResponse(api_key=api_key_masked, api_secret=api_secret_masked)

@app.post("/api/auth/keys")
def api_update_keys(request: UserKeysRequest, current_user: dict = Depends(get_current_user)):
    try:
        update_user_keys(current_user["id"], request.api_key, request.api_secret)
        return {"status": "success", "message": "API keys updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Gagal memperbarui API keys: {str(e)}")

# ────────────────────────────── Dashboard Endpoints ──────────────────────────────

@app.get("/api/portfolio", response_model=PortfolioSummaryResponse)
def api_portfolio_summary(current_user: dict = Depends(get_current_user)):
    """Get the latest portfolio summary for the current user."""
    return get_portfolio_summary(current_user["id"])

@app.get("/api/positions", response_model=List[PositionResponse])
def api_active_positions(current_user: dict = Depends(get_current_user)):
    """Get all open trading positions for the current user."""
    return get_active_positions(current_user["id"])

@app.get("/api/signals", response_model=List[SignalResponse])
def api_recent_signals(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """Get the most recent AI generated signals."""
    return get_recent_signals(limit)

@app.get("/api/volume", response_model=List[VolumeAnomalyResponse])
def api_volume_anomalies(limit: int = 20, current_user: dict = Depends(get_current_user)):
    """Get the most recent detected volume anomalies."""
    return get_volume_anomalies(limit)

@app.get("/api/equity", response_model=List[ChartDataPoint])
def api_equity_curve(days: int = None, current_user: dict = Depends(get_current_user)):
    """Get the historical equity curve data for charting for the current user."""
    return get_equity_curve(current_user["id"], days)

@app.get("/api/candles/{symbol}", response_model=List[CandleResponse])
def api_candles(symbol: str, timeframe: str = "1h", limit: int = 100, current_user: dict = Depends(get_current_user)):
    """Get historical OHLCV candles for charting."""
    symbol = symbol.replace('-', '/').upper()
    return get_latest_candles(symbol, timeframe, limit)

@app.get("/api/trades", response_model=List[TradeHistoryResponse])
def api_trade_history(limit: int = 50, current_user: dict = Depends(get_current_user)):
    """Get all trade history (open + closed), newest first, for the current user."""
    return get_trade_history(current_user["id"], limit)

@app.get("/api/daily-target", response_model=DailyTargetResponse)
def api_daily_target(current_user: dict = Depends(get_current_user)):
    """Get today's trading target status and progress for the current user."""
    return get_daily_target_status(current_user["id"])

