from typing import Dict, Any, List

SUPPORTED_LANGUAGES = {
    "en-US": {"name": "English", "native": "English", "flag": "🇬🇧"},
    "hi-IN": {"name": "Hindi", "native": "हिन्दी", "flag": "🇮🇳"},
    "te-IN": {"name": "Telugu", "native": "తెలుగు", "flag": "🇮🇳"},
    "ta-IN": {"name": "Tamil", "native": "தமிழ்", "flag": "🇮🇳"},
    "mr-IN": {"name": "Marathi", "native": "मराठी", "flag": "🇮🇳"}
}

UI_TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en-US": {
        "appHeading": "AI Thermal Event Intelligence",
        "appSubheading": "NASA FIRMS · OSM · Copernicus Multi-Layer Platform",
        "sysOnline": "SYSTEM ACTIVE",
        "navDash": "DASHBOARD",
        "navMap": "GEOSPATIAL MAP",
        "navPredict": "AI PREDICTOR",
        "navAlerts": "CRITICAL ALERTS",
        "navDb": "EVENT DATABASE",
        "navLogin": "LOGIN / REGISTER",
        "lblTotalSources": "TOTAL THERMAL SOURCES",
        "lblIndFires": "INDUSTRIAL FIRES",
        "lblForestFires": "FOREST / WILDFIRES",
        "lblAgriFires": "AGRICULTURAL BURNS",
        "lblOtherFires": "OTHER / MONITORED",
        "lblSelectState": "SELECT STATE",
        "lblEventType": "EVENT TYPE",
        "lblMinConf": "MIN CONFIDENCE (%)",
        "lblLandcover": "LANDCOVER TYPE",
        "lblSearchId": "SEARCH ID",
        "lblResetBtn": "RESET ALL FILTERS",
        "lblMapHeading": "GEOSPATIAL THERMAL HOTSPOT TRACKER",
        "lblPredictHeading": "AI THERMAL SOURCE PREDICTOR",
        "lblPredictBtn": "RUN REAL-TIME INFERENCE",
        "lblAlertsHeading": "HIGH-PRIORITY INCIDENT QUEUE",
        "lblDispatchBtn": "DISPATCH NATIONAL BRIEF (NDMA)",
        "lblDbHeading": "NATIONAL THERMAL LOGS ARCHIVE",
        "voicePrompt": "Press Voice Control and say a command (e.g. 'Show Odisha', 'Filter Industrial')...",
        "micLabel": "VOICE CONTROL",
        "listening": "Listening..."
    },
    "hi-IN": {
        "appHeading": "एआई थर्मल इवेंट इंटेलिजेंस",
        "appSubheading": "नासा फर्म्स · ओएसएम · कोपरनिकस मल्टी-लेयर प्लेटफॉर्म",
        "sysOnline": "सिस्टम सक्रिय",
        "navDash": "डैशबोर्ड",
        "navMap": "भू-स्थानिक मानचित्र",
        "navPredict": "एआई प्रेडिक्टर",
        "navAlerts": "महत्वपूर्ण अलर्ट",
        "navDb": "घटना डेटाबेस",
        "navLogin": "लॉगिन / रजिस्टर",
        "lblTotalSources": "कुल थर्मल स्रोत",
        "lblIndFires": "औद्योगिक आग",
        "lblForestFires": "जंगल / दावानल",
        "lblAgriFires": "कृषि पराली दहन",
        "lblOtherFires": "अन्य / सामान्य",
        "lblSelectState": "राज्य चुनें",
        "lblEventType": "घटना का प्रकार",
        "lblMinConf": "न्यूनतम विश्वास (%)",
        "lblLandcover": "भूमि आवरण का प्रकार",
        "lblSearchId": "आईडी खोजें",
        "lblResetBtn": "फ़िल्टर रीसेट करें",
        "lblMapHeading": "भू-स्थानिक थर्मल हॉटस्पॉट ट्रैकर",
        "lblPredictHeading": "एआई थर्मल स्रोत वर्गीकरण",
        "lblPredictBtn": "तत्काल एआई विश्लेषण चलाएं",
        "lblAlertsHeading": "राष्ट्रीय आपातकालीन अलर्ट कतार",
        "lblDispatchBtn": "एनडीएमए को अलर्ट भेजें",
        "lblDbHeading": "राष्ट्रीय थर्मल लॉग पुरालेख",
        "voicePrompt": "वॉयस कंट्रोल दबाएं और बोलें (उदा. 'ओडिशा दिखाओ', 'औद्योगिक आग')...",
        "micLabel": "वॉयस कंट्रोल",
        "listening": "सुन रहा हूँ..."
    },
    "te-IN": {
        "appHeading": "AI థర్మల్ ఈవెంట్ ఇంటెలిజెన్స్",
        "appSubheading": "నాసా FIRMS · OSM · కోపర్నికస్ మల్టీ-లేయర్ ప్లాట్‌ఫారమ్",
        "sysOnline": "సిస్టమ్ యాక్టివ్",
        "navDash": "డాష్‌బోర్డ్",
        "navMap": "భౌగోళిక మ్యాప్",
        "navPredict": "AI అంచనా వేదిక",
        "navAlerts": "తీవ్ర హెచ్చరికలు",
        "navDb": "ఈవెంట్ డేటాబేస్",
        "navLogin": "లాగిన్ / రిజిస్టర్",
        "lblTotalSources": "మొత్తం ఉష్ణ వనరులు",
        "lblIndFires": "పారిశ్రామిక మంటలు",
        "lblForestFires": "అడవి / దావానలాలు",
        "lblAgriFires": "వ్యవసాయ మంటలు",
        "lblOtherFires": "ఇతర / పర్యవేక్షణ",
        "lblSelectState": "రాష్ట్రాన్ని ఎంచుకోండి",
        "lblEventType": "ఈవెంట్ రకం",
        "lblMinConf": "కనీస విశ్వసనీయత (%)",
        "lblLandcover": "భూమి కవరేజ్ రకం",
        "lblSearchId": "శోధన ID",
        "lblResetBtn": "ఫిల్టర్‌లను రీసెట్ చేయండి",
        "lblMapHeading": "భౌగోళిక థర్మల్ హాట్‌స్పాట్ ట్రాకర్",
        "lblPredictHeading": "AI థర్మల్ మూలాల అంచనా",
        "lblPredictBtn": "విశ్లేషణను ప్రారంభించండి",
        "lblAlertsHeading": "జాతీయ అత్యవసర హెచ్చరికలు",
        "lblDispatchBtn": "NDMA కి హెచ్చరిక పంపండి",
        "lblDbHeading": "జాతీయ రికార్డుల ఆర్కైవ్",
        "voicePrompt": "వాయిస్ కంట్రోల్ క్లిక్ చేసి మాట్లాడండి (ఉదా. 'Show Odisha', 'Industrial Fires')...",
        "micLabel": "వాయిస్ కంట్రోల్",
        "listening": "వింటున్నాను..."
    },
    "ta-IN": {
        "appHeading": "AI வெப்ப நிகழ்வு நுண்ணறிவு",
        "appSubheading": "நாசா FIRMS · OSM · கோபர்னிகஸ் பல அடுக்கு தளம்",
        "sysOnline": "அமைப்பு செயலில் உள்ளது",
        "navDash": "டாஷ்போர்டு",
        "navMap": "புவிசார் வரைபடம்",
        "navPredict": "AI கணிப்பாளர்",
        "navAlerts": "முக்கிய எச்சரிக்கைகள்",
        "navDb": "நிகழ்வு தரவுத்தளம்",
        "navLogin": "உள்நுழைவு / பதிவு",
        "lblTotalSources": "மொத்த வெப்ப ஆதாரங்கள்",
        "lblIndFires": "தொழில்துறை தீ",
        "lblForestFires": "காட்டுத்தீ",
        "lblAgriFires": "விவசாயத் தீ",
        "lblOtherFires": "பிற / கண்காணிக்கப்பட்டது",
        "lblSelectState": "மாநிலத்தைத் தேர்ந்தெடுக்கவும்",
        "lblEventType": "நிகழ்வு வகை",
        "lblMinConf": "குறைந்தபட்ச நம்பிக்கை (%)",
        "lblLandcover": "நிலப்பரப்பு வகை",
        "lblSearchId": "தேடல் ஐடி",
        "lblResetBtn": "வடிப்பான்களை மீட்டமை",
        "lblMapHeading": "புவிசார் வெப்ப ஹாட்ஸ்பாட் கண்காணிப்பு",
        "lblPredictHeading": "AI வெப்ப மூல கணிப்பு",
        "lblPredictBtn": "பகுப்பாய்வை இயக்கவும்",
        "lblAlertsHeading": "அவசர எச்சரிக்கைகள்",
        "lblDispatchBtn": "NDMA க்கு எச்சரிக்கை அனுப்பு",
        "lblDbHeading": "தேசிய வெப்ப பதிவுகள்",
        "voicePrompt": "குரல் கட்டுப்பாட்டை அழுத்தி கட்டளையிடவும்...",
        "micLabel": "குரல் கட்டுப்பாடு",
        "listening": "கேட்கிறது..."
    },
    "mr-IN": {
        "appHeading": "एआय थर्मल इव्हेंट इंटेलिजन्स",
        "appSubheading": "नासा FIRMS · OSM · कोपर्निकस मल्टी-लेयर प्लॅटफॉर्म",
        "sysOnline": "प्रणाली सक्रिय",
        "navDash": "डॅशबोर्ड",
        "navMap": "भौगोलिक नकाशा",
        "navPredict": "एआय प्रेडिक्टर",
        "navAlerts": "गंभीर इशारे",
        "navDb": "इव्हेंट डेटाबेस",
        "navLogin": "लॉगिन / नोंदणी",
        "lblTotalSources": "एकूण थर्मल स्त्रोत",
        "lblIndFires": "औद्योगिक आग",
        "lblForestFires": "जंगलातील वणवा",
        "lblAgriFires": "शेतीतील आग",
        "lblOtherFires": "इतर / निरीक्षण",
        "lblSelectState": "राज्य निवडा",
        "lblEventType": "इव्हेंट प्रकार",
        "lblMinConf": "किमान विश्वास (%)",
        "lblLandcover": "जमिनीचा प्रकार",
        "lblSearchId": "आयडी शोधा",
        "lblResetBtn": "फिल्टर रीसेट करा",
        "lblMapHeading": "थर्मल हॉटस्पॉट ट्रॅकर",
        "lblPredictHeading": "एआय थर्मल स्त्रोत वर्गीकरण",
        "lblPredictBtn": "विश्लेषण चालवा",
        "lblAlertsHeading": "राष्ट्रीय आपत्कालीन अलर्ट",
        "lblDispatchBtn": "एनडीएमए कडे पाठवा",
        "lblDbHeading": "राष्ट्रीय थर्मल नोंदी",
        "voicePrompt": "व्हॉइस कंट्रोल दाबा आणि बोला...",
        "micLabel": "व्हॉइस कंट्रोल",
        "listening": "ऐकत आहे..."
    }
}

class LanguageService:
    def get_supported_languages(self) -> Dict[str, Any]:
        return {"total": len(SUPPORTED_LANGUAGES), "languages": SUPPORTED_LANGUAGES}

    def get_translations(self, lang_code: str = "en-US") -> Dict[str, Any]:
        translations = UI_TRANSLATIONS.get(lang_code, UI_TRANSLATIONS["en-US"])
        return {
            "lang": lang_code,
            "language_meta": SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES["en-US"]),
            "translations": translations
        }

    def translate_report(self, text: str, target_lang: str) -> str:
        """
        Helper to translate classification explanation or alert text into local Indian languages.
        """
        if target_lang == "hi-IN":
            replacements = {
                "Industrial": "औद्योगिक",
                "Forest/Natural": "जंगल / दावानल",
                "Agricultural": "कृषि पराली",
                "High Risk": "अत्यधिक जोखिम",
                "Medium Risk": "मध्यम जोखिम",
                "Low Risk": "सामान्य स्थिति"
            }
        elif target_lang == "te-IN":
            replacements = {
                "Industrial": "పారిశ్రామిక",
                "Forest/Natural": "అడవి మంటలు",
                "Agricultural": "వ్యవసాయం",
                "High Risk": "తీవ్ర ప్రమాదం",
                "Medium Risk": "మధ్యస్థ ప్రమాదం",
                "Low Risk": "సాధారణం"
            }
        else:
            return text

        result = text
        for k, v in replacements.items():
            result = result.replace(k, v)
        return result

language_service = LanguageService()
