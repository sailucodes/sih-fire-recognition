import os
from pathlib import Path

try:
    from pydantic_settings import BaseSettings
except ImportError:
    try:
        from pydantic import BaseSettings
    except ImportError:
        class BaseSettings:
            def __init__(self, **kwargs):
                for k, v in self.__class__.__dict__.items():
                    if not k.startswith("_") and k.isupper():
                        env_val = os.getenv(k)
                        if env_val is not None:
                            try:
                                if isinstance(v, int):
                                    setattr(self, k, int(env_val))
                                elif isinstance(v, float):
                                    setattr(self, k, float(env_val))
                                elif isinstance(v, bool):
                                    setattr(self, k, env_val.lower() in ("true", "1", "yes"))
                                elif isinstance(v, Path):
                                    setattr(self, k, Path(env_val))
                                else:
                                    setattr(self, k, env_val)
                            except Exception:
                                setattr(self, k, env_val)
                        else:
                            setattr(self, k, v)
                for k, v in kwargs.items():
                    setattr(self, k, v)

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
    
    # Server Network Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    BACKEND_PORT: int = 8000
    
    class Config:
        case_sensitive = True

settings = Settings()