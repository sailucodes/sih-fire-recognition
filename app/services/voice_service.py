import re
from typing import Dict, Any

STATE_ALIASES = {
    "Andhra Pradesh": ["andhra pradesh", "andhra", "आंध्र प्रदेश", "ఆంధ్రప్రదేశ్", "ஆந்திரப் பிரதேசம்"],
    "Arunachal Pradesh": ["arunachal pradesh", "arunachal", "अरुणाचल प्रदेश", "అరుణాచల్ ప్రదేశ్", "அருணாச்சலப் பிரதேசம்"],
    "Assam": ["assam", "asom", "असम", "అస్సాం", "அசாம்"],
    "Bihar": ["bihar", "बिहार", "బీహార్", "பீகார்"],
    "Chhattisgarh": ["chhattisgarh", "chattisgarh", "छत्तीसगढ़", "ఛత్తీస్‌గఢ్", "சத்தீஸ்கர்"],
    "Goa": ["goa", "गोवा", "గోవా", "கோவா"],
    "Gujarat": ["gujarat", "गुजरात", "గుజరాత్", "குஜராத்"],
    "Haryana": ["haryana", "हरियाणा", "హర్యానా", "ஹரியானா"],
    "Himachal Pradesh": ["himachal pradesh", "himachal", "हिमाचल प्रदेश", "హిమాచల్ ప్రదేశ్", "இமாச்சலப் பிரதேசம்"],
    "Jharkhand": ["jharkhand", "झारखंड", "ఝార్ఖండ్", "ஜார்கண்ட்"],
    "Karnataka": ["karnataka", "कर्नाटक", "కర్ణాటక", "கர்நாடகா"],
    "Kerala": ["kerala", "केरल", "కేరళ", "கேரளா"],
    "Madhya Pradesh": ["madhya pradesh", "mp", "मध्य प्रदेश", "మధ్యప్రదేశ్", "மத்தியப் பிரதேசம்"],
    "Maharashtra": ["maharashtra", "महाराष्ट्र", "మహారాష్ట్ర", "மகாராஷ்டிரா"],
    "Manipur": ["manipur", "मणिपुर", "మణిపూర్", "மணிப்பூர்"],
    "Meghalaya": ["meghalaya", "मेघालय", "మేఘాలయ", "மேகாலயா"],
    "Mizoram": ["mizoram", "मिजोरम", "మిజోరం", "மிசோரம்"],
    "Nagaland": ["nagaland", "नागालैंड", "నాగాలాండ్", "நாகாலாந்து"],
    "Odisha": ["odisha", "orissa", "ओडिशा", "उड़ीसा", "ఒడిశా", "ஒடிசா"],
    "Punjab": ["punjab", "पंजाब", "పంజాబ్", "பஞ்சாப்"],
    "Rajasthan": ["rajasthan", "राजस्थान", "రాజస్థాన్", "ராஜஸ்தான்"],
    "Sikkim": ["sikkim", "सिक्किम", "సిక్కిం", "சிக்கிம்"],
    "Tamil Nadu": ["tamil nadu", "tamilnadu", "तमिलनाडु", "తమిళనాడు", "தமிழ்நாடு"],
    "Telangana": ["telangana", "तेलंगाना", "తెలంగాణ", "தெலுங்கானா"],
    "Tripura": ["tripura", "त्रिपुरा", "త్రిపుర", "திரிபுரா"],
    "Uttar Pradesh": ["uttar pradesh", "up", "उत्तर प्रदेश", "ఉత్తరప్రదేశ్", "உத்தரப் பிரதேசம்"],
    "Uttarakhand": ["uttarakhand", "उत्तराखंड", "ఉత్తరాఖండ్", "உத்தரகண்ட்"],
    "West Bengal": ["west bengal", "bengal", "पश्चिम बंगाल", "పశ్చిమ బెంగాల్", "மேற்கு வங்காளம்"]
}

TYPE_ALIASES = {
    "Industrial": ["industrial", "factory", "refinery", "power plant", "mine", "औद्योगिक", "कारखाना", "పారిశ్రామిక", "தொழில்துறை"],
    "Forest/Natural": ["forest", "wildfire", "jungle", "जंगल", "दावानल", "అడవి", "காடு"],
    "Agricultural": ["agricultural", "crop", "stubble", "farm", "कृषि", "पराली", "వ్యవసాయ", "விவசாயம்"],
    "Other": ["other", "monitored", "सामान्य", "अन्य", "ఇతర"]
}

class VoiceService:
    def process_voice_command(self, transcript: str, lang: str = "en-US") -> Dict[str, Any]:
        """
        Parses a speech recognition transcript and extracts intent, parameters, and voice reply.
        """
        cmd = transcript.lower().strip()
        result = {
            "raw_command": transcript,
            "language": lang,
            "intent": "UNKNOWN",
            "action": None,
            "params": {},
            "voice_response": "Command received."
        }

        # 1. Check State Filter Intent
        for state, aliases in STATE_ALIASES.items():
            if any(alias in cmd for alias in aliases):
                proper_state = state.title()
                result["intent"] = "FILTER_STATE"
                result["action"] = "set_state_filter"
                result["params"] = {"state": proper_state}
                result["voice_response"] = f"Filtering thermal map for {proper_state}."
                return result

        # 2. Check Event Type Filter Intent
        for ev_type, aliases in TYPE_ALIASES.items():
            if any(alias in cmd for alias in aliases):
                result["intent"] = "FILTER_TYPE"
                result["action"] = "set_type_filter"
                result["params"] = {"event_type": ev_type}
                result["voice_response"] = f"Filtering events for {ev_type}."
                return result

        # 3. Check Reset Intent
        if any(word in cmd for word in ["reset", "clear", "all", "रीसेट", "हटाओ", "రీసెట్"]):
            result["intent"] = "RESET_FILTERS"
            result["action"] = "reset_all_filters"
            result["voice_response"] = "All filters have been reset to national view."
            return result

        # 4. Check Alert Dispatch Intent
        if any(word in cmd for word in ["alert", "dispatch", "ndma", "send", "अलर्ट", "भेजो", "హెచ్చరిక"]):
            result["intent"] = "DISPATCH_ALERT"
            result["action"] = "dispatch_national_alert"
            result["voice_response"] = "Critical thermal briefing dispatched to National Authority."
            return result

        # 5. Check Coordinate Prediction Intent
        coords = re.findall(r"[-+]?\d*\.\d+|\d+", cmd)
        if len(coords) >= 2:
            try:
                lat = float(coords[0])
                lon = float(coords[1])
                result["intent"] = "RUN_PREDICTION"
                result["action"] = "predict_point"
                result["params"] = {"latitude": lat, "longitude": lon}
                result["voice_response"] = f"Evaluating thermal risk at coordinates {lat}, {lon}."
                return result
            except ValueError:
                pass

        result["voice_response"] = "I did not recognize that command. Try saying 'Show Odisha' or 'Filter Industrial'."
        return result

voice_service = VoiceService()
