import io
import os
import logging
import requests as http_requests
from typing import List
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from crop_detector import detect_crop_disease
from claude_agent import get_sell_hold_advice, get_diagnosis_explanation

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

app = FastAPI(title="KrishiMitra API", version="1.0.0")

# ── In-memory outbreak store ──────────────────────────────────────────────────
# Keyed by region (state). Each entry is a list of individual scan records.
# Format: { region: [{ disease, severity, confidence, timestamp }, ...] }
_outbreak_store: dict[str, list] = {}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Canonical list of Indian states/UTs — mirrors the frontend dropdown
INDIAN_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
    "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim",
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand",
    "West Bengal", "Andaman and Nicobar Islands", "Chandigarh",
    "Dadra and Nagar Haveli and Daman and Diu", "Delhi (NCT)",
    "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
]

# Normalisation aliases for common OWM mis-spellings or alternate names
_STATE_ALIASES: dict[str, str] = {
    "delhi": "Delhi (NCT)",
    "jammu and kashmir": "Jammu and Kashmir",
    "j&k": "Jammu and Kashmir",
    "uttaranchal": "Uttarakhand",
    "orissa": "Odisha",
    "pondicherry": "Puducherry",
    "dadra & nagar haveli": "Dadra and Nagar Haveli and Daman and Diu",
    "daman and diu": "Dadra and Nagar Haveli and Daman and Diu",
    "andaman & nicobar islands": "Andaman and Nicobar Islands",
}


def _match_state(raw: str) -> str:
    """Case-insensitive best-match from OWM state name → canonical dropdown value."""
    if not raw:
        return raw
    low = raw.strip().lower()
    # Exact alias hit
    if low in _STATE_ALIASES:
        return _STATE_ALIASES[low]
    # Case-insensitive exact match in canonical list
    for s in INDIAN_STATES:
        if s.lower() == low:
            return s
    # Partial / substring match (e.g. "Karnataka" inside "North Karnataka")
    for s in INDIAN_STATES:
        if low in s.lower() or s.lower() in low:
            return s
    # Fall back to returning the raw value so the user at least sees something
    return raw.strip().title()


class AdviceRequest(BaseModel):
    crop: str
    region: str
    city: str | None = ""
    price: int
    severity: str


class YieldLossRequest(BaseModel):
    crop: str
    affected_area: float
    severity: str


@app.get("/health")
def health():
    return {"status": "ok", "message": "KrishiMitra backend is running"}


@app.post("/analyze-crop")
async def analyze_crop(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Please upload a file.")
    if not file.content_type or not file.content_type.startswith("image"):
        raise HTTPException(status_code=400, detail="Please upload a valid image file.")

    result = detect_crop_disease(file)
    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    ai_exp = get_diagnosis_explanation(
        disease_name=result.get("disease", "Unknown"),
        severity=result.get("severity", "moderate"),
        confidence=float(result.get("confidence", 80.0)),
    )
    result["ai_explanation"] = ai_exp if ai_exp else result.get("treatment", "")
    return result


def _log_to_outbreak_store(disease: str, severity: str, confidence: float, region: str = "Unknown") -> None:
    """Log a single scan result into the in-memory outbreak store."""
    import datetime
    entry = {
        "disease": disease,
        "severity": severity,
        "confidence": confidence,
        "timestamp": datetime.datetime.utcnow().isoformat(),
    }
    if region not in _outbreak_store:
        _outbreak_store[region] = []
    _outbreak_store[region].append(entry)
    logger.info("Outbreak store updated: region=%s disease=%s severity=%s", region, disease, severity)


@app.post("/analyze-field")
async def analyze_field(files: List[UploadFile] = File(...)):
    """
    Multi-photo Field Scan endpoint.
    Calls detect_crop_disease() on each uploaded image (same logic as /analyze-crop),
    then aggregates results into a single field health summary.

    Health score methodology:
      - "Healthy" in disease name → 100 pts (substring check on lowercased label)
      - severity == 'mild'       → 75 pts  (some concern but recoverable)
      - severity == 'moderate'   → 45 pts  (significant impact)
      - severity == 'severe'     → 15 pts  (critical; low floor, not 0, to avoid harsh rounding)
    field_health_score = mean of per-photo scores (0–100).

    Partial failures: images that fail content-type checks or raise errors in
    detect_crop_disease() are skipped and counted in `skipped_photos`.
    """
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one image file for field scan.")

    individual_results = []
    disease_counts: dict[str, int] = {}
    severity_order = {"none": 0, "healthy": 0, "mild": 1, "moderate": 2, "severe": 3}
    worst_severity_level = 0
    total_score = 0.0
    skipped = 0

    for file in files:
        # ── Guard: must be an image ───────────────────────────────────────
        ct = file.content_type or ""
        if not file.filename or not ct.startswith("image"):
            skipped += 1
            logger.warning("Field scan: skipped '%s' — not an image (content_type=%s)", file.filename, ct)
            continue

        # ── Run detection (detect_crop_disease reads file.file internally) ─
        try:
            res = detect_crop_disease(file)
        except Exception as exc:
            skipped += 1
            logger.error("Field scan: detection raised for '%s': %s", file.filename, exc)
            continue

        if res.get("error"):
            skipped += 1
            logger.warning("Field scan: skipped '%s' — detection error: %s", file.filename, res["error"])
            continue

        # ── Enrich with Claude explanation ────────────────────────────────
        ai_exp = get_diagnosis_explanation(
            disease_name=res.get("disease", "Unknown"),
            severity=res.get("severity", "moderate"),
            confidence=float(res.get("confidence", 80.0)),
        )
        res["ai_explanation"] = ai_exp if ai_exp else res.get("treatment", "")
        res["filename"] = file.filename

        individual_results.append(res)

        # ── Aggregate ─────────────────────────────────────────────────────
        disease_name = res.get("disease", "Unknown")
        disease_counts[disease_name] = disease_counts.get(disease_name, 0) + 1

        sev = str(res.get("severity", "mild")).lower()
        level = severity_order.get(sev, 1)
        if level > worst_severity_level:
            worst_severity_level = level

        if "healthy" in disease_name.lower():
            total_score += 100.0
        elif sev == "mild":
            total_score += 75.0
        elif sev == "moderate":
            total_score += 45.0
        else:  # severe or unknown
            total_score += 15.0

        # ── Log into shared outbreak store (same store as single-photo flow) ─
        _log_to_outbreak_store(
            disease=disease_name,
            severity=sev,
            confidence=float(res.get("confidence", 0)),
            region="Field Scan",  # no region context available in batch upload
        )

    if not individual_results:
        raise HTTPException(
            status_code=400,
            detail=f"Could not process any valid images in the upload batch ({skipped} skipped).",
        )

    total_count = len(individual_results)
    # 'healthy' is determined by substring match on the disease label (set by DISEASE_CATALOG
    # in crop_detector.py: the 'healthy' key maps to 'Healthy Foliage (No Disease Detected)').
    healthy_count = sum(1 for r in individual_results if "healthy" in r.get("disease", "").lower())
    affected_count = total_count - healthy_count

    field_health_score = round(total_score / total_count, 1)
    avg_confidence = round(sum(r.get("confidence", 0) for r in individual_results) / total_count, 1)

    # Most common *disease* (healthy excluded from primary rank if any diseased plants found)
    affected_counts = {k: v for k, v in disease_counts.items() if "healthy" not in k.lower()}
    if affected_counts:
        most_common_disease = max(affected_counts, key=affected_counts.get)
    elif disease_counts:
        most_common_disease = max(disease_counts, key=disease_counts.get)
    else:
        most_common_disease = "Healthy Foliage"

    rev_severity_map = {0: "Healthy / None", 1: "mild", 2: "moderate", 3: "severe"}
    worst_severity = rev_severity_map.get(worst_severity_level, "mild")

    logger.info(
        "Field scan complete: %d processed, %d skipped, score=%.1f%%, worst=%s",
        total_count, skipped, field_health_score, worst_severity,
    )

    return {
        "field_health_score": field_health_score,
        "total_photos": total_count,
        "skipped_photos": skipped,
        "healthy_count": healthy_count,
        "affected_count": affected_count,
        "most_common_disease": most_common_disease,
        "average_confidence": avg_confidence,
        "worst_severity": worst_severity,
        "disease_breakdown": disease_counts,
        "individual_results": individual_results,
    }



@app.post("/get-advice")
async def get_advice(payload: AdviceRequest):
    if not payload.crop or not payload.region or payload.price is None:
        raise HTTPException(status_code=400, detail="Missing required fields: crop, region, price")
    if payload.severity.lower() not in {"none", "mild", "moderate", "severe"}:
        raise HTTPException(status_code=400, detail="Severity must be one of: none, mild, moderate, severe")
    if payload.price < 0:
        raise HTTPException(status_code=400, detail="Price must be positive")

    return get_sell_hold_advice(
        crop_name=payload.crop,
        disease_severity=payload.severity,
        current_price=payload.price,
        region=payload.region,
        city=payload.city or "",
    )


@app.post("/yield-loss")
async def estimate_loss(payload: YieldLossRequest):
    if not payload.crop:
        raise HTTPException(status_code=400, detail="Crop is required")
    if not 0 <= payload.affected_area <= 100:
        raise HTTPException(status_code=400, detail="Affected area must be between 0 and 100")

    severity_factor = {"none": 0.05, "mild": 0.12, "moderate": 0.22, "severe": 0.35}.get(payload.severity.lower(), 0.2)
    
    # Typical yield benchmark in tons per hectare/acre for major Indian crops
    base_yield_map = {
        "rice": 25, "wheat": 28, "maize": 24, "tomato": 18, "onion": 22, "potato": 20,
        "brinjal": 16, "cabbage": 20, "cauliflower": 15, "chili": 10, "groundnut": 12,
        "soybean": 14, "sugarcane": 70, "cotton": 12, "coconut": 16, "banana": 30,
        "mango": 12, "grapes": 18, "turmeric": 14, "ginger": 15, "tea": 8,
        "coffee": 6, "jute": 16, "mustard": 11, "gram": 10, "tur dal": 9,
        "moong": 8, "okra": 12, "cucumber": 14, "garlic": 10
    }
    base_yield = base_yield_map.get(payload.crop.lower(), 16)
    
    estimated_loss_pct = round(min(90.0, payload.affected_area * severity_factor), 1)
    estimated_yield_loss = round(base_yield * (estimated_loss_pct / 100), 1)
    
    # Calculate revenue loss based on crop price
    unit_price = {"sugarcane": 3.5, "tea": 210, "coffee": 280, "garlic": 160, "turmeric": 140}.get(payload.crop.lower(), 35)
    # Revenue loss in Thousands INR
    estimated_revenue_loss = round(estimated_yield_loss * 1000 * (unit_price / 10), 2)
    potential_savings = round(estimated_revenue_loss * 0.45, 2)

    return {
        "estimated_yield_loss": f"{estimated_yield_loss} tons",
        "estimated_revenue_loss": f"₹{estimated_revenue_loss:,.2f}",
        "potential_savings": f"₹{potential_savings:,.2f}",
    }


class ReverseGeocodeRequest(BaseModel):
    lat: float
    lon: float


@app.post("/reverse-geocode")
async def reverse_geocode(payload: ReverseGeocodeRequest):
    """
    Convert lat/lon → { state, city } using OpenWeatherMap Geocoding API.
    Uses the same WEATHER_API_KEY already present in .env — no new key required.
    """
    api_key = os.getenv("WEATHER_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Reverse geocoding unavailable: WEATHER_API_KEY not configured on the server.",
        )

    url = "http://api.openweathermap.org/geo/1.0/reverse"
    params = {"lat": payload.lat, "lon": payload.lon, "limit": 5, "appid": api_key}

    try:
        resp = http_requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        results = resp.json()
    except http_requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Geocoding service timed out. Please select location manually.")
    except http_requests.exceptions.RequestException as exc:
        logger.error("OWM reverse geocode error: %s", exc)
        raise HTTPException(status_code=502, detail="Geocoding service unavailable. Please select location manually.")

    # Filter to India only
    india_results = [r for r in results if r.get("country", "").upper() == "IN"]
    if not india_results:
        raise HTTPException(
            status_code=404,
            detail="Location not recognised as being within India. Please select state and city manually.",
        )

    best = india_results[0]
    raw_state = best.get("state", "")
    city = best.get("name", "")

    matched_state = _match_state(raw_state)

    logger.info("Reverse geocode %.4f,%.4f → city=%s state=%s (raw=%s)", payload.lat, payload.lon, city, matched_state, raw_state)

    return {"state": matched_state, "city": city}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))