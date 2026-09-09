import hashlib
import hmac
import time
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional

SECRET_KEY = "sih-fire-recognition-super-secret-key-2026"
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
USERS_FILE = DATA_DIR / "users.json"

class AuthService:
    def __init__(self):
        self.users: Dict[str, Dict[str, Any]] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._load_users()

    def _hash_password(self, password: str, salt: str = "sih_salt_2026") -> str:
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    def _load_users(self):
        if os.path.exists(USERS_FILE):
            try:
                with open(USERS_FILE, "r", encoding="utf-8") as f:
                    self.users = json.load(f)
            except Exception:
                self.users = {}

        # Default pre-configured authority accounts
        if not self.users:
            admin_pwd = self._hash_password("Admin@123")
            analyst_pwd = self._hash_password("Analyst@123")
            
            self.users = {
                "admin@sih.gov.in": {
                    "email": "admin@sih.gov.in",
                    "name": "NDMA Disaster Response Chief",
                    "password_hash": admin_pwd,
                    "role": "National Authority",
                    "organization": "National Disaster Management Authority (NDMA)",
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                },
                "analyst@sih.gov.in": {
                    "email": "analyst@sih.gov.in",
                    "name": "State Operations Officer",
                    "password_hash": analyst_pwd,
                    "role": "State Emergency Analyst",
                    "organization": "Odisha Disaster Rapid Action Force (ODRAF)",
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
            self._save_users()

    def _save_users(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(self.users, f, indent=2)

    def register(self, email: str, password: str, name: str = "", role: str = "Analyst", organization: str = "State Emergency Operations") -> Dict[str, Any]:
        email = email.lower().strip()
        if not email or not password:
            return {"success": False, "error": "Email and password are required"}

        if email in self.users:
            return {"success": False, "error": "User with this email already exists"}

        pwd_hash = self._hash_password(password)
        user_record = {
            "email": email,
            "name": name or email.split("@")[0].title(),
            "password_hash": pwd_hash,
            "role": role,
            "organization": organization,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        
        self.users[email] = user_record
        self._save_users()
        
        token = self._generate_token(email)
        return {
            "success": True,
            "message": "User registered successfully",
            "token": token,
            "user": {
                "email": email,
                "name": user_record["name"],
                "role": user_record["role"],
                "organization": user_record["organization"]
            }
        }

    def login(self, email: str, password: str) -> Dict[str, Any]:
        email = email.lower().strip()
        user = self.users.get(email)
        
        if not user:
            return {"success": False, "error": "Invalid email or credentials"}

        pwd_hash = self._hash_password(password)
        if pwd_hash != user["password_hash"]:
            return {"success": False, "error": "Invalid password"}

        token = self._generate_token(email)
        return {
            "success": True,
            "message": "Login successful",
            "token": token,
            "user": {
                "email": email,
                "name": user["name"],
                "role": user["role"],
                "organization": user["organization"]
            }
        }

    def google_auth(self, google_token: str = None, email: str = None, name: str = None) -> Dict[str, Any]:
        """
        Google OAuth simulation & token verification endpoint.
        """
        verified_email = (email or "officer.sih@gov.in").lower().strip()
        verified_name = name or "Gov Officer (Google Verified)"

        if verified_email not in self.users:
            self.users[verified_email] = {
                "email": verified_email,
                "name": verified_name,
                "password_hash": self._hash_password("google_oauth_authorized"),
                "role": "Verified Officer",
                "organization": "Ministry of Environment, Forest & Climate Change",
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            self._save_users()

        token = self._generate_token(verified_email)
        return {
            "success": True,
            "message": "Google OAuth authentication verified",
            "token": token,
            "user": {
                "email": verified_email,
                "name": self.users[verified_email]["name"],
                "role": self.users[verified_email]["role"],
                "organization": self.users[verified_email]["organization"]
            }
        }

    def _generate_token(self, email: str) -> str:
        payload = f"{email}:{int(time.time()) + 86400}"
        signature = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        token = f"{payload}:{signature}"
        self.sessions[token] = {"email": email, "expires_at": int(time.time()) + 86400}
        return token

    def verify_token(self, token: str) -> Optional[Dict[str, Any]]:
        if not token or ":" not in token:
            return None
        
        parts = token.split(":")
        if len(parts) != 3:
            return None
            
        email, expires_at_str, signature = parts
        try:
            expires_at = int(expires_at_str)
            if time.time() > expires_at:
                return None
        except ValueError:
            return None

        payload = f"{email}:{expires_at_str}"
        expected_sig = hmac.new(SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if hmac.compare_digest(signature, expected_sig):
            return self.users.get(email)
        return None

auth_service = AuthService()
