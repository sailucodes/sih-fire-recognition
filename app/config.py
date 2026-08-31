from pydantic_settings import BaseSettings
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Based Industrial Fire & Persistent Thermal Source Detection System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Data Paths
    DATA_DIR: Path = BASE_DIR / "data"
    MODEL_DIR: Path = BASE_DIR / "data" / "models"
    CSV_DATA_PATH: Path = BASE_DIR / "data" / "event_classification_features.csv"
    INFRASTRUCTURE_JSON_PATH: Path = BASE_DIR / "data" / "industrial_infrastructure.json"
    MODEL_PATH: Path = BASE_DIR / "data" / "models" / "event_type_model.pkl"
    FEATURES_PATH: Path = BASE_DIR / "data" / "models" / "event_type_features.pkl"
    
    # NASA FIRMS API Config
    NASA_FIRMS_MAP_KEY: str = "DEMO_KEY"
    FIRMS_BASE_URL: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"
    
    # Clustering Parameters (DBSCAN Spatial eps in km, temporal span in hours)
    SPATIAL_CLUSTER_RADIUS_KM: float = 1.5
    TEMPORAL_WINDOW_HOURS: int = 168 # 7 days
    
    class Config:
        case_sensitive = True

settings = Settings()