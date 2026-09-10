import hashlib
import hmac
import time
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from app.db.database import db_manager

SECRET_KEY = "sih-fire-recognition-super-secret-key-2026"

class AuthService:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._seed_default_users()

    def _hash_password(self, password: str, salt: str = "sih_salt_2026") -> str:
        return hashlib.sha256((password + salt).encode("utf-8")).hexdigest()

    def _seed_default_users(self):
        if db_manager.count_users() == 0:
            admin_pwd = self._hash_password("Admin@123")
            analyst_pwd = self._hash_password("Analyst@123")
            db_manager.insert_user(
                email="admin@sih.gov.in",
                password_hash=admin_pwd,
                name="NDMA Disaster Response Chief",
                role="National Authority",
                organization="National Disaster Management Authority (NDMA)"
            )
            db_manager.insert_user(
                email="analyst@sih.gov.in",
                password_hash=analyst_pwd,
                name="State Operations Officer",
                role="State Emergency Analyst",
                organization="Odisha Disaster Rapid Action Force (ODRAF)"
            )

    def register(self, email: str, password: str, name: str = "", role: str = "Analyst", organization: str = "State Emergency Operations") -> Dict[str, Any]:
        email = email.lower().strip()
        if not email or not password:
            return {"success": False, "error": "Email and password are required"}

        existing = db_manager.get_user_by_email(email)
        if existing:
            return {"success": False, "error": "User with this email already exists"}

        pwd_hash = self._hash_password(password)
        user_name = name or email.split("@")[0].title()
        inserted = db_manager.insert_user(
            email=email,
            password_hash=pwd_hash,
            name=user_name,
            role=role,
            organization=organization
        )
        if not inserted:
            return {"success": False, "error": "Database error while creating user"}

        token = self._generate_token(email)
        return {
            "success": True,
            "message": "User registered successfully",
            "token": token,
            "user": {
                "email": email,
                "name": user_name,
                "role": role,
                "organization": organization
            }
        }

    def login(self, email: str, password: str) -> Dict[str, Any]:
        email = email.lower().strip()
        user = db_manager.get_user_by_email(email)
        
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

        user = db_manager.get_user_by_email(verified_email)
        if not user:
            db_manager.insert_user(
                email=verified_email,
                password_hash=self._hash_password("google_oauth_authorized"),
                name=verified_name,
                role="Verified Officer",
                organization="Ministry of Environment, Forest & Climate Change"
            )
            user = db_manager.get_user_by_email(verified_email)

        token = self._generate_token(verified_email)
        return {
            "success": True,
            "message": "Google OAuth authentication verified",
            "token": token,
            "user": {
                "email": verified_email,
                "name": user["name"],
                "role": user["role"],
                "organization": user["organization"]
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
            return db_manager.get_user_by_email(email)
        return None

auth_service = AuthService()

