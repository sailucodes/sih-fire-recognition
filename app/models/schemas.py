from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from enum import Enum

class EventTypeEnum(str, Enum):
    INDUSTRIAL = "Industrial"
    FOREST_NATURAL = "Forest/Natural"
    AGRICULTURAL = "Agricultural"
    OTHER = "Other"

class FacilityTypeEnum(str, Enum):
    REFINERY = "refinery"
    POWERPLANT = "powerplant"
    MINE = "mine"
    INDUSTRIAL_AREA = "industrial_area"
    UNKNOWN = "unknown"

class HotspotPoint(BaseModel):
    latitude: float = Field(..., description="Latitude coordinate in WGS84")
    longitude: float = Field(..., description="Longitude coordinate in WGS84")
    frp: Optional[float] = Field(5.0, description="Fire Radiative Power (MW)")
    brightness: Optional[float] = Field(320.0, description="Brightness temperature (Kelvin)")
    acq_date: Optional[str] = Field("2026-08-25", description="Acquisition date (YYYY-MM-DD)")
    acq_time: Optional[str] = Field("1200", description="Acquisition time (HHMM UTC)")
    satellite: Optional[str] = Field("VIIRS", description="Satellite sensor (VIIRS, MODIS)")
    confidence: Optional[str] = Field("nominal", description="Detection confidence")
    daynight: Optional[str] = Field("D", description="Day (D) or Night (N) detection")

class SingleClassifyRequest(BaseModel):
    latitude: float = Field(..., ge=-90.0, le=90.0, example=22.34236)
    longitude: float = Field(..., ge=-180.0, le=180.0, example=69.87119)
    frp: Optional[float] = Field(12.5, description="Fire Radiative Power in MW", example=15.0)
    brightness: Optional[float] = Field(345.0, description="Brightness temperature in Kelvin", example=350.0)
    landcover_class: Optional[str] = Field(None, description="Optional Landcover class (e.g. Built-up, Cropland, Tree cover)")
    detection_count: Optional[int] = Field(1, description="Number of recurring detections observed at location")
    active_days: Optional[int] = Field(1, description="Number of unique active days")

class ClassificationResponse(BaseModel):
    source_id: Optional[str] = None
    latitude: float
    longitude: float
    predicted_event_type: EventTypeEnum
    confidence_pct: float
    probabilities: Dict[str, float]
    is_persistent_thermal_source: bool
    is_flare_anomaly: bool
    risk_level: str
    nearest_facility_type: str
    nearest_facility_name: Optional[str]
    nearest_facility_distance_km: float
    landcover_class: str
    explanation: List[str]

class ThermalSourceSummary(BaseModel):
    source_id: str
    latitude: float
    longitude: float
    event_type: str
    predicted_event_type: str
    confidence_pct: float
    total_detections: int
    active_days: int
    mean_frp: float
    max_frp: float
    nearest_facility_type: str
    nearest_facility_name: Optional[str] = None
    min_distance_to_industry_km: float
    landcover_class: str
    first_detection: Optional[str] = None
    last_detection: Optional[str] = None
    is_persistent: bool
    is_flare_anomaly: bool
    risk_level: str

class GeoJSONGeometry(BaseModel):
    type: str = "Point"
    coordinates: List[float] # [longitude, latitude]

class GeoJSONFeature(BaseModel):
    type: str = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]

class GeoJSONFeatureCollection(BaseModel):
    type: str = "FeatureCollection"
    features: List[GeoJSONFeature]

class InfrastructureFacility(BaseModel):
    id: str
    name: str
    type: str
    latitude: float
    longitude: float
    state: Optional[str] = None
    country: Optional[str] = "India"
    risk_category: Optional[str] = None
    capacity: Optional[str] = None

class AnalyticsSummary(BaseModel):
    total_thermal_sources: int
    industrial_sources: int
    industrial_percentage: float
    forest_natural_sources: int
    forest_percentage: float
    agricultural_sources: int
    agricultural_percentage: float
    other_sources: int
    other_percentage: float
    persistent_sources_count: int
    high_risk_anomalies_count: int
    average_mean_frp: float
    max_recorded_frp: float

class TimelineDataPoint(BaseModel):
    date: str
    industrial_count: int
    forest_count: int
    agricultural_count: int
    other_count: int
    total_frp: float

class AlertItem(BaseModel):
    alert_id: str
    source_id: str
    timestamp: str
    latitude: float
    longitude: float
    event_type: str
    severity: str # "INFO", "WARNING", "CRITICAL"
    title: str
    message: str
    facility_context: Optional[str]